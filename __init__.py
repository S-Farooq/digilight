

from flask import Flask, request, redirect, g, render_template, Markup, session, url_for
import sys
reload(sys)
sys.setdefaultencoding('utf-8')

import hili as hili
from flask_uploads import UploadSet, configure_uploads, IMAGES
from evernote.api.client import EvernoteClient

app = Flask(__name__)
from config import SECRET_KEY, EVERNOTE_DEV_TOKEN, EN_CONSUMER_KEY, EN_CONSUMER_SECRET, DEBUG

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
        session['access_token']=access_token
    except KeyError:
        files = session['orig_filenames']
        return render_msg(files[0], "<h2>ERROR: Couldn't authenticate your account...</h2>")

    files_to_attach=session['orig_filenames']
    note_msg = process_note(session['notetitle'], session['ocr_text'],files_to_attach)
    return render_msg(UPLOAD_FOLDER+files_to_attach[0], note_msg)
    
def render_msg(filename,msg):
    msgmrkup=Markup(msg)
    return render_template("index.html", note_msg=msgmrkup, file_path=UPLOAD_FOLDER+filename,scroll="contact")

def render_result(filename,result):
    return render_template("index.html", output_print=result, 
            file_path=UPLOAD_FOLDER+filename,scroll="contact")


def process_images(files, highlighted=True):
    contoured_imgs = []
    if highlighted:
        for filename in files:
            contoured_img = hili.contour_img(UPLOAD_PATH+filename)
            if contoured_img:
                contoured_imgs.append(contoured_img)
    else:
        for filename in files:
            contoured_imgs.append(filename)

    all_texts=[]
    for image_file in contoured_imgs:
        json_data, text =hili.google_ocr_img(UPLOAD_PATH+image_file)
        all_texts.append(text)

    ocr_text = "\n---------------------\n".join(all_texts)
    
    return contoured_imgs, ocr_text


def process_note(notetitle,ocr_text,files):
    file_list = []
    for f in files:
        file_list.append(UPLOAD_PATH+f)
    access_token = session['access_token']
    
    msg, notecontent = hili.create_note_from_highlight(access_token,file_list, 
        ocr_text.strip(), ocr=False, notetitle=notetitle)

    if len(notecontent)>100:
        tmp = notecontent[:100]
        notecontent = tmp + "..."
    note_msg="<h2>{msg}</h2><p>{notecontent}</p>".format(msg=msg,notecontent=notecontent)
    return note_msg
        
@app.route('/')
def my_form():
    # session.clear()
    return render_template('index.html')

@app.route('/', methods=['GET', 'POST'])
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
        highlighted=True
        filename = photos.save(request.files['images'])
        files = [filename]
        session['orig_filenames']=files
        contoured_imgs, ocr_text = process_images(files,highlighted=highlighted)
        if len(contoured_imgs)==0:
            return render_msg(files[0], "<h2>Sorry! Nothing detected, try another image</h2>")
        
        session['contoured_imgs']=contoured_imgs
        return render_result(contoured_imgs[0],ocr_text)
        
    elif request.form['btn'] == 'createnote':
        session['notetitle'] = request.form['title']
        session['ocr_text'] = request.form['content']
        try:
            access_token = session['access_token']
        except:
            return auth()
        files_to_attach=session['orig_filenames']
        if DEBUG:
            files_to_attach=session['contoured_imgs']
        note_msg = process_note(session['notetitle'], session['ocr_text'],files_to_attach)
        return render_msg(files_to_attach[0], note_msg)
        
    elif request.form['btn'] == 'lucky' and request.method == 'POST' and 'images' in request.files:
        highlighted=True
        filename = photos.save(request.files['images'])
        files = [filename]
        contoured_imgs, ocr_text = process_images(files,highlighted=highlighted)
        if len(contoured_imgs)==0:
            return render_msg(files[0], "<h2>Sorry! Nothing detected, try another image</h2>")
        
        try:
            access_token = session['access_token']
        except:
            session['orig_filenames']=files
            session['contoured_imgs']=contoured_imgs
            session['notetitle'] = ''
            session['ocr_text'] = ocr_text
            return auth()
        
        note_msg = process_note('', ocr_text,files)
        return render_msg(files[0], note_msg)
        
    # elif request.form['btn'] == 'sample':
    #     filename = "highlight-sample_1.jpg"
    #     contoured_img = hili.contour_img(UPLOAD_PATH+filename)
    #     if not contoured_img:
    #         msg=Markup("<h2>Sorry! Nothing detected, try another image</h2>")
    #         return render_template("index.html", note_msg=msg, file_path=str(UPLOAD_FOLDER+filename),scroll="contact")
    #     api_res, ocr_texts = hili.google_ocr_img(UPLOAD_PATH+contoured_img)

    #     session['filename']=contoured_img
    #     session['orig_filename']=filename
    #     return render_template("index.html", output_print="\n".join(ocr_texts), file_path=str(UPLOAD_FOLDER+contoured_img),scroll="contact")
    else:
        return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True, port=80)
    main()

