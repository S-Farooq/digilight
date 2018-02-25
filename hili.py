import sys

sys.path.append('/usr/local/lib/python2.7/site-packages')
sys.path.append('/lib/x86_64-linux-gnu')
sys.path.append('/')    
import json, base64, binascii,hashlib
from evernote.api.client import EvernoteClient
import evernote.edam.type.ttypes as Types
import evernote.edam.error.ttypes as Errors

import requests

import cv2
import numpy as np

def convert_img_to_json(input_file):
    """Translates the input file into a json output file.

    Args:
        input_file: a file object, containing lines of input to convert.
        output_filename: the name of the file to output the json to.
    """
    request_list = []
    for line in input_file:
        image_filename, features = line.lstrip().split(' ', 1)

        with open(image_filename, 'rb') as image_file:
            content_json_obj = {
                'content': base64.b64encode(image_file.read()).decode('UTF-8')
            }

        feature_json_obj = []
        for word in features.split(' '):
            feature, max_results = word.split(':', 1)
            feature_json_obj.append({
                'type': get_detection_type(feature),
                'maxResults': int(max_results),
            })

        request_list.append({
            'features': feature_json_obj,
            'image': content_json_obj,
        })

    return {'requests': request_list}


DETECTION_TYPES = [
    'TYPE_UNSPECIFIED',
    'FACE_DETECTION',
    'LANDMARK_DETECTION',
    'LOGO_DETECTION',
    'LABEL_DETECTION',
    'TEXT_DETECTION',
    'SAFE_SEARCH_DETECTION',
    'DOCUMENT_TEXT_DETECTION'
]


def get_detection_type(detect_num):
    """Return the Vision API symbol corresponding to the given number."""
    detect_num = int(detect_num)
    if 0 < detect_num < len(DETECTION_TYPES):
        return DETECTION_TYPES[detect_num]
    else:
        return DETECTION_TYPES[0]

def contour_img(img_path):
    cropped_hili_img = "static/uploads/testimg.png"
    image = cv2.imread(img_path)

    # rgb to HSV color spave conversion
    hsv_img = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

    HSV_lower = np.array([22, 50, 50], np.uint8)  # Lower HSV value
    HSV_upper = np.array([30, 250, 250], np.uint8)  # Upper HSV value

    frame_threshed = cv2.inRange(hsv_img, HSV_lower, HSV_upper)
    # find connected components
    _, contours, hierarchy, = cv2.findContours(frame_threshed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)

    # Draw contours around filtered objects
    thresh = 100  # Noise removal threshold
    OutputImg = image.copy()
    max_thresh = max([len(x) for x in contours])
    mask = np.zeros_like(image)  # Create mask where white is what we want, black otherwise
    out = np.zeros_like(image)  # Extract out the object and place into output image

    for cnt in contours:
        # remove noise objects having contour length threshold value
        if len(cnt) > thresh:
            cv2.drawContours(OutputImg, [cnt], 0, (0, 0, 255), 2)
            cv2.drawContours(mask, [cnt], 0, (255,255,255), -1)  # Draw filled contour in mask

    out[mask == 255] = image[mask == 255]
    imgray = cv2.cvtColor(out, cv2.COLOR_BGR2GRAY)
    cv2.imwrite(cropped_hili_img, imgray)
    return "testimg.jpg"
    

def google_ocr_img(img_path):
    data = convert_img_to_json([img_path+" 7:5"])
    return str(data)
    response = requests.post(url='https://vision.googleapis.com/v1/images:annotate?key=AIzaSyCRCwqeqr8FMivse-xvpSqAsnJvHeDAGvk',
        data=data,
        headers={'Content-Type': 'application/json'})

    api_result = response.json()
    return api_result
    

def create_en_resource(filename):
    # Calculate the md5 hash of the pdf
    md5 = hashlib.md5()
    with open(filename, "rb") as imageFile:
        pdf_bytes = imageFile.read()
    md5.update(pdf_bytes)
    md5hash = md5.hexdigest()

    # Create the Data type for evernote that goes into a resource
    pdf_data = Types.Data()
    pdf_data.bodyHash = md5hash
    pdf_data.size = len(pdf_bytes)
    pdf_data.body = pdf_bytes

    # Create a resource for the note that contains the pdf
    pdf_resource = Types.Resource()
    pdf_resource.data = pdf_data
    pdf_resource.mime = "image/jpg"

    # Create a resource list to hold the pdf resource
    resource_list = []
    resource_list.append(pdf_resource)
    return resource_list

def makeNote(authToken, noteStore, noteTitle, noteBody, resources=[], parentNotebook=None):
    """
    Create a Note instance with title and body
    Send Note object to user's account
    """

    ourNote = Types.Note()
    ourNote.title = noteTitle

    ## Build body of note

    nBody = "<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
    nBody += "<!DOCTYPE en-note SYSTEM \"http://xml.evernote.com/pub/enml2.dtd\">"
    nBody += "<en-note>%s" % noteBody
    if resources:
        ### Add Resource objects to note body
        nBody += "<br />" * 2
        ourNote.resources = resources
        for resource in resources:
            hexhash = resource.data.bodyHash
            nBody += "Attachment with hash %s: <br /><en-media type=\"%s\" hash=\"%s\" /><br />" % \
                (hexhash, resource.mime, hexhash)
    nBody += "</en-note>"

    ourNote.content = nBody

    ## parentNotebook is optional; if omitted, default notebook is used
    if parentNotebook and hasattr(parentNotebook, 'guid'):
        ourNote.notebookGuid = parentNotebook.guid

    ## Attempt to create note in Evernote account
    try:
        note = noteStore.createNote(authToken, ourNote)
    except Errors.EDAMUserException, edue:
        ## Something was wrong with the note data
        ## See EDAMErrorCode enumeration for error code explanation
        ## http://dev.evernote.com/documentation/reference/Errors.html#Enum_EDAMErrorCode
        print "EDAMUserException:", edue
        return None
    except Errors.EDAMNotFoundException, ednfe:
        ## Parent Notebook GUID doesn't correspond to an actual notebook
        print "EDAMNotFoundException: Invalid parent notebook GUID"
        return None
    ## Return created note object
    return note

def get_all_text(gcloud_data):
    # print gcloud_data
    all_texts = []
    for textAnnotations in gcloud_data['responses']:
        all_texts.append(textAnnotations['fullTextAnnotation']['text'].encode('ascii','ignore'))

    return all_texts

def create_note_from_highlight(image_file):
    json_data=google_ocr_img(image_file)
    # json_data=open("jsons/api_result.json").read()

    # data = json.loads(json_data)
    all_texts = get_all_text(data)

    dev_token = "S=s1:U=946af:E=1691629fdb0:C=161be78cfa0:P=1cd:A=en-devtoken:V=2:H=62d05bfbbde1b056b12169ea273b31ce"
    client = EvernoteClient(token=dev_token)
    userStore = client.get_user_store()
    user = userStore.getUser()


    noteStore = client.get_note_store()
    notebooks = noteStore.listNotebooks()
    for n in notebooks:
        if n.name=='hilis':
            parentNotebook=n

    try:
        resources = create_en_resource(image_file)
        makeNote(dev_token, noteStore, "Test-HILI", "\n\n".join(all_texts),
                 parentNotebook=parentNotebook, resources=resources)
    except:
        return "ERROR: Couldnt make evernote out of " + "\n\n".join(all_texts)  
          
    return "\n\n".join(all_texts)