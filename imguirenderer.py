import ctypes
import os
from pathlib import Path
import imgui
import pyglet
from pyglet import gl, clock
from pyglet.window import key, mouse
from arcade.gl import BufferDescription, Context
import arcade
from imgui.integrations import compute_fb_scale
from imgui.integrations.base import BaseOpenGLRenderer
import imgui.core


class ArcadeGLRenderer(BaseOpenGLRenderer):
    """
    A renderer using the arcade.gl module instead of PyOpenGL.
    This is using pyglet's OpenGL bindings instead.
    """

    VERTEX_SHADER_SRC = """
    #version 330
    uniform mat4 ProjMtx;
    in vec2 Position;
    in vec2 UV;
    in vec4 Color;
    out vec2 Frag_UV;
    out vec4 Frag_Color;
    void main() {
        Frag_UV = UV;
        Frag_Color = Color;
        gl_Position = ProjMtx * vec4(Position.xy, 0, 1);
    }
    """

    FRAGMENT_SHADER_SRC = """
    #version 330
    uniform sampler2D Texture;
    in vec2 Frag_UV;
    in vec4 Frag_Color;
    out vec4 Out_Color;
    void main() {
        Out_Color = Frag_Color * texture(Texture, Frag_UV.st);
    }
    """

    def __init__(self, window, *args, **kwargs):
        self._window = window
        self._ctx: Context = window.ctx
        self._program = None
        self._vao = None
        self._vbo = None
        self._ibo = None
        self._font_texture = None

        super().__init__()

    def render(self, draw_data):
        io = self.io    

        display_width, display_height = io.display_size
        display_fb_scale = io.display_fb_scale
        fb_width = int(display_width * display_fb_scale[0])
        fb_height = int(display_height * display_fb_scale[1])

        if fb_width == 0 or fb_height == 0:
            return

        self._program["ProjMtx"] = (
            2.0 / fb_width, 0.0, 0.0, 0.0,
            0.0, 2.0 / -fb_height, 0.0, 0.0,
            0.0, 0.0, -1.0, 0.0,
            -1.0, 1.0, 0.0, 1.0,
        )

        draw_data.scale_clip_rects(*display_fb_scale)

        self._ctx.enable_only(self._ctx.BLEND)
        self._ctx.blend_func = self._ctx.BLEND_DEFAULT

        self._font_texture.use(0)

        for commands in draw_data.commands_lists:
            # Write the vertex and index buffer data without copying it
            vtx_type = ctypes.c_byte * commands.vtx_buffer_size * imgui.VERTEX_SIZE
            idx_type = ctypes.c_byte * commands.idx_buffer_size * imgui.INDEX_SIZE
            vtx_arr = (vtx_type).from_address(commands.vtx_buffer_data)
            idx_arr = (idx_type).from_address(commands.idx_buffer_data)
            self._vbo.write(vtx_arr)
            self._ibo.write(idx_arr)

            idx_pos = 0
            for command in commands.commands:
                # Use low level pyglet call here instead because we only have the texture name
                gl.glBindTexture(gl.GL_TEXTURE_2D, command.texture_id)

                # Set scissor box
                x, y, z, w = command.clip_rect
                self._ctx.scissor = int(x), int(fb_height - w), int(z - x), int(w - y)

                self._vao.render(self._program, mode=self._ctx.TRIANGLES, vertices=command.elem_count, first=idx_pos)
                idx_pos += command.elem_count

        # Just reset scissor back to default/viewport
        self._ctx.scissor = None

    def refresh_font_texture(self):
        width, height, pixels = self.io.fonts.get_tex_data_as_rgba32()
        # Old font texture will be GCed if exist
        self._font_texture = self._ctx.texture((width, height), components=4, data=pixels)
        self.io.fonts.texture_id = self._font_texture.glo
        self.io.fonts.clear_tex_data()

    def _create_device_objects(self):
        self._program = self._ctx.program(
            vertex_shader=self.VERTEX_SHADER_SRC,
            fragment_shader=self.FRAGMENT_SHADER_SRC,
        )
        self._program["Texture"] = 0
        self._vbo = self._ctx.buffer(reserve=imgui.VERTEX_SIZE * 65536)
        self._ibo = self._ctx.buffer(reserve=imgui.INDEX_SIZE * 65536)
        # NOTE: imgui.INDEX_SIZE is type size for the index buffer. We might need to support 8 and 16 bit
        # but right now we are assuming 32 bit
        self._vao = self._ctx.geometry(
            [
                BufferDescription(
                    self._vbo,
                    "2f 2f 4f1",
                    ("Position", "UV", "Color"),
                    normalized=("Color",)
                ),
            ],
            index_buffer = self._ibo,
        )           

    def _invalidate_device_objects(self):
        # NOTE: OpenGL resource will automatically be released
        self._font_texture = None
        self._vbo = None
        self._ibo = None
        self._vao = None
        self._program = None
        self.io.fonts.texture_id = 0

    def shutdown(self):
        self._invalidate_device_objects()


class PygletMixin:
    REVERSE_KEY_MAP = {
        key.TAB: imgui.KEY_TAB,
        key.LEFT: imgui.KEY_LEFT_ARROW,
        key.RIGHT: imgui.KEY_RIGHT_ARROW,
        key.UP: imgui.KEY_UP_ARROW,
        key.DOWN: imgui.KEY_DOWN_ARROW,
        key.PAGEUP: imgui.KEY_PAGE_UP,
        key.PAGEDOWN: imgui.KEY_PAGE_DOWN,
        key.HOME: imgui.KEY_HOME,
        key.END: imgui.KEY_END,
        key.DELETE: imgui.KEY_DELETE,
        key.SPACE: imgui.KEY_SPACE,
        key.BACKSPACE: imgui.KEY_BACKSPACE,
        key.RETURN: imgui.KEY_ENTER,
        key.ESCAPE: imgui.KEY_ESCAPE,
        key.A: imgui.KEY_A,
        key.C: imgui.KEY_C,
        key.V: imgui.KEY_V,
        key.X: imgui.KEY_X,
        key.Y: imgui.KEY_Y,
        key.Z: imgui.KEY_Z,
    }

    def _set_pixel_ratio(self, window):
        window_size = window.get_size()
        self.io.display_size = window_size
        # It is conceivable that the pyglet version will not be solely
        # determinant of whether we use the fixed or programmable, so do some
        # minor introspection here to check.
        if hasattr(window, 'get_viewport'):
            viewport = window.get_viewport()
            viewport_size = viewport[1] - viewport[0], viewport[3] - viewport[2]
            self.io.display_fb_scale = compute_fb_scale(window_size, viewport_size)
        elif hasattr(window, 'get_pixel_ratio'):
            self.io.display_fb_scale = (window.get_pixel_ratio(),
                                        window.get_pixel_ratio())
        else:
            # Default to 1.0 in this unlikely circumstance
            self.io.display_fb_scale = (1.0, 1.0)

    def _attach_callbacks(self, window):
        window.push_handlers(
            self.on_mouse_motion,
            self.on_key_press,
            self.on_key_release,
            self.on_text,
            self.on_mouse_drag,
            self.on_mouse_press,
            self.on_mouse_release,
            self.on_mouse_scroll,
            self.on_resize,
        )

    def _map_keys(self):
        key_map = self.io.key_map

        # note: we cannot use default mechanism of mapping keys
        #       because pyglet uses weird key translation scheme
        for value in self.REVERSE_KEY_MAP.values():
            key_map[value] = value

    def _on_mods_change(self, mods):
        self.io.key_ctrl = mods & key.MOD_CTRL
        self.io.key_super = mods & key.MOD_COMMAND
        self.io.key_alt = mods & key.MOD_ALT
        self.io.key_shift = mods & key.MOD_SHIFT

    def on_mouse_motion(self, x, y, dx, dy):
        self.io.mouse_pos = x, self.io.display_size.y - y

    def on_key_press(self, key_pressed, mods):
        if key_pressed in self.REVERSE_KEY_MAP:
            self.io.keys_down[self.REVERSE_KEY_MAP[key_pressed]] = True
        self._on_mods_change(mods)

    def on_key_release(self, key_released, mods):
        if key_released in self.REVERSE_KEY_MAP:
            self.io.keys_down[self.REVERSE_KEY_MAP[key_released]] = False
        self._on_mods_change(mods)

    def on_text(self, text):
        io = imgui.get_io()

        for char in text:
            io.add_input_character(ord(char))

    def on_mouse_drag(self, x, y, dx, dy, button, modifiers):
        self.io.mouse_pos = x, self.io.display_size.y - y

        if button == mouse.LEFT:
            self.io.mouse_down[0] = 1

        if button == mouse.RIGHT:
            self.io.mouse_down[1] = 1

        if button == mouse.MIDDLE:
            self.io.mouse_down[2] = 1

    def on_mouse_press(self, x, y, button, modifiers):
        self.io.mouse_pos = x, self.io.display_size.y - y

        if button == mouse.LEFT:
            self.io.mouse_down[0] = 1

        if button == mouse.RIGHT:
            self.io.mouse_down[1] = 1

        if button == mouse.MIDDLE:
            self.io.mouse_down[2] = 1

    def on_mouse_release(self, x, y, button, modifiers):
        self.io.mouse_pos = x, self.io.display_size.y - y

        code = 0; delay = .2
        if button == mouse.LEFT:
            delay = 0
        elif button == mouse.RIGHT:
            code = 1
        elif button == mouse.MIDDLE:
            code = 2
        # Need a slight delay for touch events
        def set_mouse(delta_time):
            self.io.mouse_down[code] = 0
        clock.schedule_once(set_mouse, delay)

    def on_mouse_scroll(self, x, y, mods, scroll):
        self.io.mouse_wheel = scroll

    def on_resize(self, width, height):
        self.io.display_size = width, height


class ArcadeRenderer(PygletMixin, ArcadeGLRenderer):
    def __init__(self, window, attach_callbacks=True):
        super().__init__(window)
        window_size = window.get_size()
        viewport = window.get_viewport()
        viewport_size = viewport[1] - viewport[0], viewport[3] - viewport[2]

        self.io.display_size = window_size
        self.io.display_fb_scale = compute_fb_scale(window_size, viewport_size)

        self._map_keys()

        if attach_callbacks:
            window.push_handlers(
                self.on_mouse_motion,
                self.on_key_press,
                self.on_key_release,
                self.on_text,
                self.on_mouse_drag,
                self.on_mouse_press,
                self.on_mouse_release,
                self.on_mouse_scroll,
                self.on_resize,
            )



class Gui:
    def __init__(self, window):
        self.window = window
        # Must create or set the context before instantiating the renderer
        imgui.create_context()
        self.renderer = ArcadeRenderer(window)

    def draw(self):
        imgui.render()
        self.renderer.render(imgui.get_draw_data())


class App(arcade.Window):

    def __init__(self,width=800, height=600, title='imgui', resizable=True):
        super().__init__()
        self.gui = Gui(self)
        self.pages = {}
        self.view_metrics = False
        self.resource_path = Path(__file__).parent.parent / 'resources'
        file_path = os.path.dirname(os.path.abspath(__file__))
        # print(file_path)
        os.chdir(file_path)
        #self.add_page(Index, "index", "Index")
        #self.show("index") 

    def add_page(self, klass, name, title):
        # print(page.__dict__)
        self.pages[name] = { 'klass': klass, 'name': name, 'title': title }

    def on_draw(self):
        super().on_draw()
        self.gui.draw()

    def run(self):
        arcade.run()

    def show(self, name):
        def callback(delta_time):
            entry = self.pages[name]
            self.page = page = entry['klass'].create(self, name, entry['title'])
            self.show_view(page)
        pyglet.clock.schedule_once(callback, 0)


class Page(arcade.View):
    def __init__(self, window, name, title):
        super().__init__(window=window)
        self.name = name
        self.title = title

    def reset(self):
        pass

    @classmethod
    def create(self, app, name, title):
        page = self(app, name, title)
        page.reset()
        return page

    def on_draw(self):
        arcade.start_render()

        imgui.new_frame()
        
        if self.window.view_metrics:
            self.window.view_metrics = imgui.show_metrics_window(closable=True)

        self.draw_mainmenu()
        self.draw_navbar()

        imgui.set_next_window_position(288, 32, imgui.ONCE)
        imgui.set_next_window_size(512, 512, imgui.ONCE)

        self.draw()
        
        imgui.end_frame()

    def on_update(self, delta_time: float):
        return self.update(delta_time)

    def draw_navbar(self):
        imgui.set_next_window_position(16, 32, imgui.ONCE)
        imgui.set_next_window_size(256, 732, imgui.ONCE)
        
        imgui.begin("Examples")

        titles = [page['title'] for page in self.window.pages.values()]
        names = [page['name'] for page in self.window.pages.values()]

        if imgui.listbox_header("Examples", -1, -1):

            for entry in self.window.pages.values():
                opened, selected = imgui.selectable(entry['title'], entry['name'] == self.window.page.name)
                if opened:
                    self.window.show(entry['name'])

            imgui.listbox_footer()
        
        imgui.end()

    def draw_mainmenu(self):
        if imgui.begin_main_menu_bar():
            # File
            if imgui.begin_menu('File', True):
                clicked_quit, selected_quit = imgui.menu_item(
                    "Quit", 'Cmd+Q', False, True
                )

                if clicked_quit:
                    exit(1)

                imgui.end_menu()
            # View
            if imgui.begin_menu('View', True):
                clicked_metrics, self.window.view_metrics = imgui.menu_item(
                    "Metrics", 'Cmd+M', self.window.view_metrics, True
                )

                imgui.end_menu()

            imgui.end_main_menu_bar()

    def draw(self):
        pass

    def update(self, delta_time):
        pass

    def rel(self, x, y):
        pos = imgui.get_cursor_screen_pos()
        x1 = pos[0] + x
        y1 = pos[1] + y
        return x1, y1


class Index(Page):
    def draw(self):
        imgui.begin("Index")
        imgui.text("Welcome to the Arcade ImGui Demo!")        
        imgui.end()

