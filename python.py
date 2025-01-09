#import pymongo
import os
import sys
import pprint
from flask import render_template
from flask import Flask, redirect, url_for, session, request, jsonify
from flask import render_template
from flask_oauthlib.contrib.apps import github
from flask_oauthlib.client import OAuth
from markupsafe import Markup 

app = Flask(__name__)

connection_string = os.environ["MONGO_CONNECTION_STRING"]
client = pymongo.MongoClient(connection_string) 
# Send a ping to confirm a successful connection
try:
    client.admin.command('ping')
    print("Pinged your deployment. You successfully connected to MongoDB!")
except Exception as e:
     print(e)

db_name = os.environ["MONGO_DBNAME"]
    
birdsDB = client[db_name]
mongoBirds = birdsDB['birds']
app.debug = True #Change this to False for production
#os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1' #Remove once done debugging

app.secret_key = os.environ['SECRET_KEY'] #used to sign session cookies
oauth = OAuth(app)
oauth.init_app(app) #initialize the app to be able to make requests for user information

#Set up GitHub as OAuth provider
github = oauth.remote_app(
    'github',
    consumer_key=os.environ['GITHUB_CLIENT_ID'], #your web app's "username" for github's OAuth
    consumer_secret=os.environ['GITHUB_CLIENT_SECRET'],#your web app's "password" for github's OAuth
    request_token_params={'scope': 'user:email'}, #request read-only access to the user's email.  For a list of possible scopes, see developer.github.com/apps/building-oauth-apps/scopes-for-oauth-apps
    base_url='https://api.github.com/',
    request_token_url=None,
    access_token_method='POST',
    access_token_url='https://github.com/login/oauth/access_token',  
    authorize_url='https://github.com/login/oauth/authorize' #URL for github's OAuth login
)
#context processors run before templates are rendered and add variable(s) to the template's context
#context processors must return a dictionary 
#this context processor adds the variable logged_in to the conext for all templates
@app.context_processor
def inject_logged_in():
    is_logged_in = 'github_token' in session #this will be true if the token is in the session and false otherwise
    return {"logged_in":is_logged_in}

@app.route('/')
def forum_login():
    if "comment" in session:
        session.pop("comment")
    if "github_token" in session:
        return redirect(url_for('forum_home'))
    else:
        return render_template('forum.html')
    
@app.route('/forum') 
def forum_home():
    if "github_token" not in session: 
        return redirect(url_for('forum_login'))
    else:
        posts = ""
        for doc in mongoBirds.find():
            posts += Markup("<p>" + str(doc["User"]) + ": " + str(doc["Message"]) + "</p>") 
    return render_template('actualforum.html', posts=posts)
 
@app.route('/createPost', methods=["GET", "POST"])
def create_post():
    if "comment" in session: 
        content = request.form['content']
        if session["comment"] != content:
            print("hi2")
            username = session['user_data']['login']
            doc = {"User":username, "Message":content }
            mongoBirds.insert_one(doc)
            session["comment"] = content 
        else:
            posts = ""
            for doc in mongoBirds.find():
                posts += Markup("<p>" + str(doc["User"]) + ": " + str(doc["Message"]) + "</p>")
            return render_template('actualforum.html', posts=posts)
    else:
        print("hi") 
        content = request.form['content']
        username = session['user_data']['login']
        doc = {"User":username, "Message":content }
        mongoBirds.insert_one(doc)
        session["comment"] = content 
    posts = ""
    for doc in mongoBirds.find():
        posts += Markup("<p>" + str(doc["User"]) + ": " + str(doc["Message"]) + "</p>")
    return render_template('actualforum.html', posts=posts)

#redirect to GitHub's OAuth page and confirm callback URL
@app.route('/login')
def login():   
    return github.authorize(callback=url_for('authorized', _external=True, _scheme='http')) #callback URL must match the pre-configured callback URL

@app.route('/logout')
def logout():
    session.clear()
    return render_template('message.html', message='You were logged out')

@app.route('/login/authorized')
def authorized():
    resp = github.authorized_response()
    if resp is None:
        session.clear()
        message = 'Access denied: reason=' + request.args['error'] + ' error=' + request.args['error_description'] + ' full=' + pprint.pformat(request.args)      
    else:
        try:
            session['github_token'] = (resp['access_token'], '') #save the token to prove that the user logged in
            session['user_data']=github.get('user').data
            #pprint.pprint(vars(github['/email']))
            #pprint.pprint(vars(github['api/2/accounts/profile/']))
            message='You were successfully logged in as ' + session['user_data']['login'] + '.'
            return redirect(url_for('forum_home'))
        except Exception as inst:
            session.clear()
            print(inst)
            message='Unable to login, please try again.  '
    return render_template('message.html', message=message)

#the tokengetter is automatically called to check who is logged in.
@github.tokengetter
def get_github_oauth_token():
    return session['github_token']








if __name__ == '__main__':
    app.run()
