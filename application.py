from flask import Flask
application = Flask(__name__)

@application.route('/')
def hello():
    return 'Hello Elastic Beanstalk!'