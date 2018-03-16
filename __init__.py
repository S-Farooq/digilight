

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

def root_dir():  # pragma: no cover
    return os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
with open('/var/www/Digilight/digilight/config.json') as json_data_file:
    data = json.load(json_data_file)
app.secret_key = data['secret_key']
#  Client Keys

photos = UploadSet('photos', IMAGES)

UPLOAD_FOLDER = 'uploads/'
UPLOAD_PATH = '/var/www/Digilight/digilight/static/'+UPLOAD_FOLDER
ALLOWED_EXTENSIONS = set(['txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'])

app.config['UPLOAD_FOLDER'] = UPLOAD_PATH
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
app.config['UPLOADED_PHOTOS_DEST'] = UPLOAD_PATH
configure_uploads(app, photos)


def get_mrkup_from_df(reco_df,to_display_amount=10):
    reco_mrkup = ["""<table class="table table-hover"><thead><tr>
        <th>{columns}</th></tr></thead><tbody>
      """.format(columns="</th><th>".join(reco_df.columns))]

    for index, row in reco_df.iterrows():
        if to_display_amount==0:
            break
        to_display_amount = to_display_amount - 1
        row = [str(x).upper() for x in row]
        reco_mrkup.append("""<tr>
        <th>{vals}</th></tr>
            """.format(vals="</th><th>".join(row)))

    reco_mrkup.append("""</tbody></table>""")
    reco_display = "\n".join(reco_mrkup)
    return reco_display


@app.route('/')
def my_form():
    session.clear()
    return render_template('index.html')

@app.route('/', methods=['GET', 'POST'])
def upload():
    if request.form['btn'] == 'submitbtn' and request.method == 'POST' and 'images' in request.files:
        filename = photos.save(request.files['images'])
        contoured_img = hili.contour_img(UPLOAD_PATH+filename)
        api_res, ocr_texts = hili.google_ocr_img(UPLOAD_PATH+contoured_img)

        session['filename']=contoured_img
        return render_template("index.html", output_print="\n".join(ocr_texts), file_path=str(UPLOAD_FOLDER+contoured_img))
    elif request.form['btn'] == 'createnote':
        file_path = UPLOAD_PATH+session['filename']
        notetitle = request.form['title']
        ocr_text = request.form['content']
        msg, ocr_texts = hili.create_note_from_highlight(file_path, [ocr_text], ocr=False, notetitle=notetitle)
        return render_template("index.html", note_msg=str(msg)+str(ocr_text), file_path=str(file_path))
    else:
        return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True, port=80)
    main()
