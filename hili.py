import sys

sys.path.append('/usr/local/lib/python2.7/site-packages')
sys.path.append('/lib/x86_64-linux-gnu')
sys.path.append('/')    
import json, base64, binascii,hashlib
from evernote.api.client import EvernoteClient
import evernote.edam.type.ttypes as Types
import evernote.edam.error.ttypes as Errors

import requests

from PIL import Image
import cv2
import numpy as np

import os 
main_path = os.path.dirname(os.path.realpath(__file__)) +"/"
from config import GOOGLE_API_KEY
from config import SECRET_KEY, EVERNOTE_DEV_TOKEN, EN_CONSUMER_KEY, EN_CONSUMER_SECRET


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

def get_evernote_client(token=None):
    if token:
        return EvernoteClient(token=token, sandbox=True)
    else:
        return EvernoteClient(
            consumer_key=EN_CONSUMER_KEY,
            consumer_secret=EN_CONSUMER_SECRET,
            sandbox=True
        )


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



def get_detection_type(detect_num):
    """Return the Vision API symbol corresponding to the given number."""
    detect_num = int(detect_num)
    if 0 < detect_num < len(DETECTION_TYPES):
        return DETECTION_TYPES[detect_num]
    else:
        return DETECTION_TYPES[0]

def custom_smoothen_cnt(cnt):
    M = cv2.moments(cnt)
    cx = int(M['m10'] / M['m00'])
    cy = int(M['m01'] / M['m00'])
    leftmost = tuple(cnt[cnt[:, :, 0].argmin()][0])
    rightmost = tuple(cnt[cnt[:, :, 0].argmax()][0])
    topmost = tuple(cnt[cnt[:, :, 1].argmin()][0])
    bottommost = tuple(cnt[cnt[:, :, 1].argmax()][0])
    print "Edge Points:", leftmost, rightmost, topmost, bottommost
    area = cv2.contourArea(cnt)
    print "AREA of Orig Contour:", area
    newcnt = cnt.copy()
    for i in range(cnt.shape[0]):
        x = cnt[i, 0, 0]
        y = cnt[i, 0, 1]
        if x>leftmost[0] and y<leftmost[1] and x<cx:
            newcnt[i, 0, 0] = leftmost[0]
        elif x<rightmost[0] and y<leftmost[1] and x<cx:
            newcnt[i, 0, 0] = rightmost[0]
    area = cv2.contourArea(newcnt)
    print "AREA of Smoothened Contour:", area
    return newcnt

def smoothen_contour(contour):
    from scipy.interpolate import splprep, splev
    x, y = contour.T
    # Convert from numpy arrays to normal arrays
    x = x.tolist()[0]
    y = y.tolist()[0]
    # https://docs.scipy.org/doc/scipy-0.14.0/reference/generated/scipy.interpolate.splprep.html
    tck, u = splprep([x, y], u=None, s=15.0, per=1)
    # https://docs.scipy.org/doc/numpy-1.10.1/reference/generated/numpy.linspace.html
    u_new = np.linspace(u.min(), u.max(), len(contour)*0.05)
    # https://docs.scipy.org/doc/scipy-0.14.0/reference/generated/scipy.interpolate.splev.html
    x_new, y_new = splev(u_new, tck, der=0)
    # Convert it back to numpy format for opencv to be able to display it
    res_array = [[[int(i[0]), int(i[1])]] for i in zip(x_new, y_new)]
    smooth_cnt = np.asarray(res_array, dtype=np.int32)
    return smooth_cnt

def expand_contour(cnt,expand_rate_x=1.1,expand_rate_y=1.05):
    M = cv2.moments(cnt)
    cx = int(M['m10'] / M['m00'])
    cy = int(M['m01'] / M['m00'])
    leftmost = tuple(cnt[cnt[:, :, 0].argmin()][0])
    rightmost = tuple(cnt[cnt[:, :, 0].argmax()][0])
    topmost = tuple(cnt[cnt[:, :, 1].argmin()][0])
    bottommost = tuple(cnt[cnt[:, :, 1].argmax()][0])
    print "Edge Points:", leftmost, rightmost, topmost, bottommost
    print "Centroid: (",cx,",",cy,")"
    area = cv2.contourArea(cnt)
    print "AREA of Contour:",area
    newcnt = cnt.copy()
    for i in range(cnt.shape[0]):
        if abs(cnt[i, 0, 0] - cx)>(abs(leftmost[0]-cx)*0.8) or abs(cnt[i, 0, 1] - cy) > (abs(topmost[1] - cy) * 0.8):
            newcnt[i, 0, 0] = ((cnt[i, 0, 0] - cx) * expand_rate_x) + cx
            newcnt[i, 0, 1] = ((cnt[i, 0, 1] - cy) * expand_rate_y) + cy

    return newcnt

def contour_img(img_path,thresh=400,std_dev=7, hsv_lower=[22, 30, 30], hsv_upper=[45, 255, 255]):
    """Returns the name of the saved contour PNG image that will be sent for OCR thru API"""
    contoured_img = "contoured_"+os.path.basename(img_path).split(".")[0]+".png"
    image = cv2.imread(img_path)

    # rgb to HSV color spave conversion
    hsv_img = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

    HSV_lower = np.array(hsv_lower, np.uint8)  # Lower HSV value
    HSV_upper = np.array(hsv_upper, np.uint8)  # Upper HSV value

    frame_threshed = cv2.inRange(hsv_img, HSV_lower, HSV_upper)
    # find connected components
    _, contours, hierarchy, = cv2.findContours(frame_threshed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)

    # Draw contours around filtered objects
    OutputImg = image.copy()
    cnt_lens = [cv2.contourArea(x) for x in contours]

    klist = cnt_lens
    avglatlist = range(0,len(cnt_lens))

    klist_np = np.array(klist).astype(np.float)
    avglatlist_np = np.array(avglatlist).astype(np.float)    

    # klist_filtered = klist_np[(abs(klist_np - np.mean(klist_np))) > (std_dev * np.std(klist_np))]
    avglatlist_filtered = avglatlist_np[(abs(klist_np - np.mean(klist_np))) > (std_dev * np.std(klist_np))]
    while len(avglatlist_filtered)==0:
        if std_dev<1.5:
            return False
            break
        std_dev=std_dev-0.5
        avglatlist_filtered = avglatlist_np[(abs(klist_np - np.mean(klist_np))) > (std_dev * np.std(klist_np))]

    max_thresh = max(cnt_lens)
    mask = np.zeros_like(image)  # Create mask where white is what we want, black otherwise
    out = np.zeros_like(image)  # Extract out the object and place into output image

    for c in avglatlist_filtered:
        # # remove noise objects having contour length threshold value
        cnt = contours[int(c)]

        if len(cnt) > thresh:
            expand_cnt = expand_contour(cnt,expand_rate_x=1.02,expand_rate_y=1.04)
            # smooth_cnt = smoothen_contour(expand_cnt)
            epsilon = 0.04*cv2.arcLength(cnt,True)
            print "Epsilon", epsilon
            smooth_cnt = cv2.approxPolyDP(expand_cnt, epsilon, False)
            # cust_smooth_cnt = custom_smoothen_cnt(cnt)
            cv2.drawContours(OutputImg, [cnt], 0, (0, 0, 50), 1)
            cv2.drawContours(OutputImg, [expand_cnt], 0, (0, 0, 255), 2)
            cv2.drawContours(OutputImg, [smooth_cnt], 0, (255, 0, 0), 2)
            # cv2.drawContours(OutputImg, [smooth_cnt], 0, (0, 255,0), 1)
            cv2.drawContours(mask, [smooth_cnt], 0, (255,255,255), -1)  # Draw filled contour in mask
            cv2.drawContours(mask, [expand_cnt], 0, (255, 255, 255), -1)  # Draw filled contour in mask


            # hull = cv2.convexHull(cnt)

    out[mask == 255] = image[mask == 255]
    out[mask == 0] = 255
    imgray = cv2.cvtColor(out, cv2.COLOR_BGR2GRAY)
    
    #save contoured image to display
    j = Image.fromarray(imgray)
    j.save(main_path+"static/uploads/"+contoured_img)

    cv2.imwrite(main_path+"static/uploads/col_"+contoured_img,OutputImg)
    return contoured_img
    

def google_ocr_img(img_path):
    """Sends DOCUMENT_TEXT_DETECTION API request with img file as content and return OCR result"""
    data = convert_img_to_json([img_path+" 7:5"])
    useragent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/55.0.2883.75 Safari/537.36'

    response = requests.post(url="https://vision.googleapis.com/v1/images:annotate?key={key}".format(key=GOOGLE_API_KEY),
        data=json.dumps(data),
        headers={'Content-Type': 'application/json',
                'User-Agent': useragent})
    api_result = response.json()
    all_texts = get_all_text(api_result) 
    return api_result, all_texts
    

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

def remove_gibberish(text):
    test = text.split(" ")
    final = []
    start=0
    end=len(test)
    for i in range(len(test)):
        x = test[i]
        if x in words.words() or x.isdigit():
            start=i
            break

    for i in range(len(test)-1,-1,-1):
        x = test[i]
        if x in words.words() or x.isdigit():
            end=i
            break

    return " ".join(final[start:end+1])

def get_all_text(gcloud_data):
    # Returns a Text Array of the OCR data going throught the Gcloud Vision API Response"""
    from nltk.corpus import words
    all_texts = []
    for textAnnotations in gcloud_data['responses']:
        text_raw = textAnnotations['fullTextAnnotation']['text'].encode('ascii','ignore')
        text = text_raw.replace("\n", " ")
        text_cleaned = remove_gibberish(text)
        
        all_texts.append(text_cleaned.strip())

    return all_texts

def create_note_from_highlight(authToken,image_file, all_texts, ocr=False, notetitle=''):
    from time import gmtime, strftime

    if notetitle=='':
        curr_time = strftime("%Y-%m-%d", gmtime())
        notetitle="digilight {curr_time}".format(curr_time=curr_time)
    
    if ocr:
        json_data, all_texts =google_ocr_img(image_file)

    note_content = "\n\n".join(all_texts)
    # json_data=open("jsons/api_result.json").read()

    # data = json.loads(json_data)
    # all_texts = get_all_text(data)

    client = get_evernote_client(authToken)
    userStore = client.get_user_store()
    user = userStore.getUser()


    noteStore = client.get_note_store()
    notebooks = noteStore.listNotebooks()
    found=False
    for n in notebooks:
        if n.name=='Digilights':
            parentNotebook=n
            found=True

    if not found:
        ourNotebook = Types.Notebook()
        ourNotebook.name = "Digilights"
        parentNotebook = noteStore.createNotebook(ourNotebook)


    try:
        resources = create_en_resource(image_file)
        note = makeNote(authToken, noteStore, notetitle, note_content,
                 parentNotebook=parentNotebook, resources=resources)
    except:
        return "ERROR: Couldnt make evernote.", note_content
    
    msg = note.title + " created in " + parentNotebook.name + "!"
    return msg, note_content

if __name__ == '__main__':
    img_path = "sample_images/highlight-sample2.jpg"
    c = contour_img(img_path, thresh=100, std_dev=7, hsv_lower=[22, 30, 30], hsv_upper=[45, 255, 255])
    print "Done:",c
