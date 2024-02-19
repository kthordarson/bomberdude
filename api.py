import flask
from flask import Flask

class ApiServer(Flask):
	def __init__(self, import_name):
		super(ApiServer, self).__init__(import_name)
		self.before_request(self.my_preprocessing)
		# Set up some logging and template paths.

	def my_preprocessing(self):
		pass
		# Do stuff to flask.request

	def get_data(self):
		return 'Hello, World!'

	async def _run(self, host, port):
		self.run(host=host, port=port)

if __name__ == '__main__':
	app = ApiServer(__name__)
	app.add_url_rule('/get_data', view_func=app.get_data, methods=['GET'])

	app.run(host='127.0.0.1', port=9699)