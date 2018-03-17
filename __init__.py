

from flask import Flask, request, redirect, g, render_template, Markup, session, url_for
import pandas as pd
import numpy as np
import sys
reload(sys)
sys.setdefaultencoding('utf-8')

import json
import base64
import urllib, difflib

import hili as hili
from flask import Flask, render_template, request
from flask.ext.uploads import UploadSet, configure_uploads, IMAGES
from evernote.api.client import EvernoteClient

def root_dir():  # pragma: no cover
    return os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
from config import SECRET_KEY, EVERNOTE_DEV_TOKEN, EN_CONSUMER_KEY, EN_CONSUMER_SECRET

app.secret_key = SECRET_KEY
#  Client Keys

# Server-side Parameters
CLIENT_SIDE_URL = "http://test.shaham.me"
REDIRECT_URI = "{}/callback/q".format(CLIENT_SIDE_URL)


photos = UploadSet('photos', IMAGES)

UPLOAD_FOLDER = 'uploads/'
UPLOAD_PATH = '/var/www/Digilight/digilight/static/'+UPLOAD_FOLDER
ALLOWED_EXTENSIONS = set(['txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'])

app.config['UPLOAD_FOLDER'] = UPLOAD_PATH
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
app.config['UPLOADED_PHOTOS_DEST'] = UPLOAD_PATH
configure_uploads(app, photos)


def auth():
    client = hili.get_evernote_client()
    callbackUrl = REDIRECT_URI
    request_token = client.get_request_token(callbackUrl)

    # Save the request token information for later
    session['oauth_token'] = request_token['oauth_token']
    session['oauth_token_secret'] = request_token['oauth_token_secret']

    # Redirect the user to the Evernote authorization URL
    return redirect(client.get_authorize_url(request_token))


@app.route("/callback/q")
def callback():
    try:
        client = hili.get_evernote_client()
        access_token  = client.get_access_token(
            session['oauth_token'],
            session['oauth_token_secret'],
            request.args.get('oauth_verifier', '')
        )
    except KeyError:
        contoured_img = session['filename']
        return render_template("index.html", note_msg=Markup("<h2>ERROR: Couldn't authenticate your account...</h2>"),
         file_path=str(UPLOAD_FOLDER+contoured_img),scroll="contact")

    contoured_img = session['filename']
    notetitle = session['notetitle']
    ocr_text = session['ocr_text']
    msg, notecontent = hili.create_note_from_highlight(access_token,file_path, 
        [ocr_text.strip()], ocr=False, notetitle=notetitle)
    note_msg="<h2>{msg}</h2><p>{notecontent}</p>".format(msg=msg,notecontent=notecontent)
    note_msg=Markup(note_msg)
    return render_template("index.html", note_msg=note_msg, file_path=str(UPLOAD_FOLDER+contoured_img),scroll="contact")    
    # return redirect(url_for('.my_form'))

@app.route('/')
def my_form():
    session.clear()
    return render_template('index.html')

@app.route('/', methods=['GET', 'POST'])
def upload():
    if request.form['btn'] == 'submitbtn' and request.method == 'POST' and 'images' in request.files:
        filename = photos.save(request.files['images'])
        contoured_img = hili.contour_img(UPLOAD_PATH+filename)
        if not contoured_img:
            msg=Markup("<h2>Sorry! Nothing detected, try another image</h2>")
            return render_template("index.html", note_msg=msg, file_path=str(UPLOAD_FOLDER+filename),scroll="contact")
        api_res, ocr_texts = hili.google_ocr_img(UPLOAD_PATH+contoured_img)
        
        session['filename']=contoured_img
        return render_template("index.html", output_print="\n".join(ocr_texts), file_path=str(UPLOAD_FOLDER+contoured_img),scroll="contact")
    elif request.form['btn'] == 'createnote':
        contoured_img = session['filename']
        file_path = UPLOAD_PATH+contoured_img
        notetitle = request.form['title']
        ocr_text = request.form['content']
        session['notetitle'] = notetitle
        session['ocr_text'] = ocr_text

        auth()
        # msg, notecontent = hili.create_note_from_highlight(client,file_path, [ocr_text.strip()], ocr=False, notetitle=notetitle)
        # note_msg="<h2>{msg}</h2><p>{notecontent}</p>".format(msg=msg,notecontent=notecontent)
        # note_msg=Markup(note_msg)
        # return render_template("index.html", note_msg=note_msg, file_path=str(UPLOAD_FOLDER+contoured_img),scroll="contact")

    elif request.form['btn'] == 'lucky' and request.method == 'POST' and 'images' in request.files:
        filename = photos.save(request.files['images'])
        contoured_img = hili.contour_img(UPLOAD_PATH+filename)
        if not contoured_img:
            msg=Markup("<h2>Sorry! Nothing detected, try another image</h2>")
            return render_template("index.html", note_msg=msg, file_path=str(UPLOAD_FOLDER+filename),scroll="contact")
        api_res, ocr_texts = hili.google_ocr_img(UPLOAD_PATH+contoured_img)

        file_path = UPLOAD_PATH+contoured_img
        notetitle = ''
        ocr_text = "\n".join(ocr_texts)
        msg, notecontent = hili.create_note_from_highlight(EVERNOTE_DEV_TOKEN,file_path, [ocr_text.strip()], ocr=False, notetitle=notetitle)
        note_msg="<h2>{msg}</h2><p>{notecontent}</p>".format(msg=msg,notecontent=notecontent)
        note_msg=Markup(note_msg)
        return render_template("index.html", note_msg=note_msg, file_path=str(UPLOAD_FOLDER+contoured_img),scroll="contact")
    elif request.form['btn'] == 'sample':
        filename = "highlight-sample_1.jpg"
        contoured_img = hili.contour_img(UPLOAD_PATH+filename)
        if not contoured_img:
            msg=Markup("<h2>Sorry! Nothing detected, try another image</h2>")
            return render_template("index.html", note_msg=msg, file_path=str(UPLOAD_FOLDER+filename),scroll="contact")
        api_res, ocr_texts = hili.google_ocr_img(UPLOAD_PATH+contoured_img)

        session['filename']=contoured_img
        return render_template("index.html", output_print="\n".join(ocr_texts), file_path=str(UPLOAD_FOLDER+contoured_img),scroll="contact")
    else:
        return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True, port=80)
    main()
