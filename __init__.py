

from flask import Flask, request, redirect, g, render_template, Markup, session, url_for
import sys, os

import time 
reload(sys)
sys.setdefaultencoding('utf-8')

import hili as hili
from werkzeug.utils import secure_filename

# from flask_uploads import UploadSet, configure_uploads, IMAGES
from evernote.api.client import EvernoteClient

app = Flask(__name__)
from config import SECRET_KEY, EVERNOTE_DEV_TOKEN, EN_CONSUMER_KEY, EN_CONSUMER_SECRET, DEBUG

app.secret_key = SECRET_KEY
app.debug = True
#  Client Keys

# Server-side Parameters
CLIENT_SIDE_URL = "http://digilight.shaham.me"
REDIRECT_URI = "{}/callback/q".format(CLIENT_SIDE_URL)


# photos = UploadSet('photos', IMAGES)

UPLOAD_FOLDER = 'uploads/'
UPLOAD_PATH = '/var/www/Digilight/digilight/static/'+UPLOAD_FOLDER
ALLOWED_EXTENSIONS = set(['png', 'jpg', 'jpeg', 'gif'])

app.config['UPLOAD_FOLDER'] = UPLOAD_PATH
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024
app.config['UPLOADED_PHOTOS_DEST'] = UPLOAD_PATH
# configure_uploads(app, photos)

from flask import send_from_directory

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'],
                               filename)
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

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
        session['access_token']=access_token
    except KeyError:
        files = session['orig_filenames']
        return render_msg(files, "<h2>ERROR: Couldn't authenticate your account...</h2>")

    files_to_attach=session['orig_filenames']
    note_msg, notecontent = process_note(session['notetitle'], session['ocr_text'],files_to_attach)
    return render_msg(files_to_attach, note_msg, tweet_text=notecontent)
    
def render_msg(filenames,msg, tweet_text=None):
    msgmrkup=Markup(msg)
    if tweet_text:
        return render_template("index.html", note_msg=msgmrkup, 
        file_path=[UPLOAD_FOLDER+f for f in filenames],scroll="contact",
        tweet=tweet_text)
            
    return render_template("index.html", note_msg=msgmrkup, 
        file_path=[UPLOAD_FOLDER+f for f in filenames],scroll="contact")

def render_result(filenames,result):
    return render_template("index.html", output_print=result, 
            file_path=[UPLOAD_FOLDER+f for f in filenames],scroll="contact",
            notetitle=session['notetitle'])


def process_images(files, highlighted=True, pre_contour=False):
    contoured_imgs = []
    if pre_contour:
        for filename in files:
            contoured_img = hili.contour_img(UPLOAD_PATH+filename)
            if contoured_img:
                contoured_imgs.append(contoured_img)
    else:
        for filename in files:
            contoured_imgs.append(filename)

    
    json_data =hili.google_ocr_img([UPLOAD_PATH+x for x in contoured_imgs])
    print "GOOGLE API RESPONDED.."
    list_of_word_obj = hili.get_word_objs(json_data)
    if highlighted:
        all_ocr_text, contoured_imgs = hili.get_post_ocr_contour_text(
            [UPLOAD_PATH+x for x in files], 
            list_of_word_obj,
            word_sel_thres = 10, 
            hili_to_word_ratio=0.65,
            check_for_intersections=False)
    else:
        all_ocr_text = hili.get_all_text(json_data)
    del list_of_word_obj

    ocr_text = "\n---------------------\n".join(all_ocr_text)
    
    return contoured_imgs, ocr_text


def process_note(notetitle,ocr_text,files):
    file_list = []
    for f in files:
        file_list.append(UPLOAD_PATH+f)
    access_token = session['access_token']
    
    msg, notecontent = hili.create_note_from_highlight(access_token,file_list, 
        ocr_text.strip(), ocr=False, notetitle=notetitle)

    limit=500
    if len(notecontent)>limit:
        tmp = notecontent[:limit]
        notecontent = tmp + "..."
    note_msg="<h2>{msg}</h2><p>{notecontent}</p>".format(msg=msg,notecontent=notecontent)

    notecontent.replace(";", "")
    notecontent.replace(":", "")
    notecontent.replace("&", "")
    return note_msg, notecontent
        
@app.route('/')
def my_form():
    # session.clear()
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    """
    TEST CASES:
    Digitize:
        - fails to digitize reporting, no contour detected
        - succeeds at digitizing
    Createnote:
        - Succeeds at note creation
        - Attaches the right file
        - shows the right msg afterwards
    Quick note create btn:
        - both of the above
    """

    if request.form['btn'] == 'submitbtn' and request.method == 'POST' and 'images' in request.files:
        # session.clear()
        highlighted=True
        session['notetitle']= ''
        if request.form['title']:
            session['notetitle'] = request.form['title']
        if request.form['option']!='highlighted_only':
            highlighted=False

        files=[]

        try:
            for f in request.files.getlist('images'):
                if f and allowed_file(f.filename):
                    filename = secure_filename(f.filename)
                    f.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    files.append(filename)
        except Exception as e:
            return render_msg(files, 
                "<h2>Sorry! File Upload failed.., contact server admin. {e}</h2>".format(e=str(e)))
        
        # files = [filename]
        session['orig_filenames']=files
        try:
            contoured_imgs, ocr_text = process_images(files,highlighted=highlighted)
        except Exception as e:
            return render_msg(files, 
                "<h2>Sorry! API process failed, contact server admin. {e}</h2>".format(e=str(e)))
        
        if len(contoured_imgs)==0:
            return render_msg(files, "<h2>Sorry! Nothing detected, try another image</h2>")
        
        session['contoured_imgs']=contoured_imgs
        return render_result(contoured_imgs,ocr_text)
        
    elif request.form['btn'] == 'createnote':
        session['notetitle'] = request.form['title']
        session['ocr_text'] = request.form['content']
        try:
            access_token = session['access_token']
        except:
            return auth()
        files_to_attach=session['orig_filenames']
        note_msg, notecontent = process_note(session['notetitle'], session['ocr_text'],files_to_attach)
        files_to_show=files_to_attach
        return render_msg(files_to_attach, note_msg, tweet_text=notecontent)
        
    elif request.form['btn'] == 'lucky' and request.method == 'POST' and 'images' in request.files:
        highlighted=True
        if request.form['option']!='highlighted_only':
            highlighted=False

        notetitle = request.form['title']

        files=[]
        try:
            for f in request.files.getlist('images'):
                if f and allowed_file(f.filename):
                    filename = secure_filename(f.filename)
                    f.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    files.append(filename)
        except Exception as e:
            return render_msg(files, 
                "<h2>Sorry! File Upload failed.., contact server admin. {e}</h2>".format(e=str(e)))
        
        try:
            contoured_imgs, ocr_text = process_images(files,highlighted=highlighted)
        except Exception as e:
            return render_msg(files, 
                "<h2>Sorry! API process failed, contact server admin. {e}</h2>".format(e=str(e)))
        
        if len(contoured_imgs)==0:
            return render_msg(files, "<h2>Sorry! Nothing detected, try another image</h2>")
        
        try:
            access_token = session['access_token']
        except:
            session['orig_filenames']=files
            session['contoured_imgs']=contoured_imgs
            session['notetitle'] = ''
            session['ocr_text'] = ocr_text
            return auth()
        
        note_msg, notecontent = process_note(notetitle, ocr_text,files)
        return render_msg(files, note_msg, tweet_text=notecontent)
        
    else:
        return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True, port=80)
    main()

