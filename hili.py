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
from config import SECRET_KEY, EVERNOTE_DEV_TOKEN, EN_CONSUMER_KEY, EN_CONSUMER_SECRET, DEBUG

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
        return EvernoteClient(token=token, sandbox=DEBUG)
    else:
        return EvernoteClient(
            consumer_key=EN_CONSUMER_KEY,
            consumer_secret=EN_CONSUMER_SECRET,
            sandbox=DEBUG
        )


def convert_img_to_json(input_file):
    """Translates the input file into a json output file.

    Args:
        input_file: a file object, containing lines of input to convert.
        output_json: the json request to send to API
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

def contour_img(img_path,thresh=400,std_dev=4, hsv_lower=[22, 30, 30], hsv_upper=[45, 255, 255]):
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
    

def google_ocr_img(img_paths):
    """Sends DOCUMENT_TEXT_DETECTION API request with img file as content and return OCR result"""
    call_commands = [img_path+" 7:5" for img_path in img_paths]
    data = convert_img_to_json(call_commands)
    useragent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/55.0.2883.75 Safari/537.36'

    response = requests.post(url="https://vision.googleapis.com/v1/images:annotate?key={key}".format(key=GOOGLE_API_KEY),
        data=json.dumps(data),
        headers={'Content-Type': 'application/json',
                'User-Agent': useragent})
    api_result = response.json()
    try:
        res = api_result['responses']
    except:
        raise Exception("Looks like API call failed..contact server admin.")
    return api_result

def get_word_objs(api_result):
    list_of_word_obj = []
    for res in api_result['responses']:
        txt_ann = res['textAnnotations']
        word_objects = []
        for x in range(len(txt_ann)):
            obj = txt_ann[x]
            if ' ' not in obj['description']:
                word_objects.append(obj)

        print "TOTAL WORDS OCR-ed:", len(word_objects)
        list_of_word_obj.append(word_objects)
    return list_of_word_obj

def get_frame_threshold(image, hsv_lower=[22, 30, 30],hsv_upper=[45, 255, 255]):
    hsv_img = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    
    HSV_lower = np.array(hsv_lower, np.uint8)  # Lower HSV value
    HSV_upper = np.array(hsv_upper, np.uint8)  # Upper HSV value

    frame_threshed = cv2.inRange(hsv_img, HSV_lower, HSV_upper)
    return frame_threshed

def swap_on_intersect(mask1, mask2, threshold=0.2):
    intersectarea = np.sum(mask1[mask2==255])/255
    area1 = np.sum(mask1)/255
    area2 = np.sum(mask2)/255
    if intersectarea>threshold*area1 or intersectarea>threshold*area2:
        print "AREA1:", area1, "AREA2:", area2, "INTERSECT_AREA:", intersectarea
        if area2<area1:
            return True, False
        else:
            return True, True
    return False, False

def get_post_ocr_contour_text(images, list_of_word_objects,
    word_sel_thres = 5, hili_to_word_ratio=0.5, check_for_intersections=False):
    assert(len(images)==len(list_of_word_objects))
    all_ocr_text = []
    all_contoured_imgs = []
    for imgnum in range(len(images)):
        img_path = images[imgnum]
        image = cv2.imread(img_path)
        frame_threshed = get_frame_threshold(image)
        word_objects = list_of_word_objects[imgnum]
        if len(word_objects)==0:
            continue

        selected_obj = []
        hili_text = []
        
        for x in range(len(word_objects[:])):
            obj=word_objects[x]
            word_objects[x]['sel'] = False
            try:
                bounding_box = obj['boundingPoly']
                box_points = [(p['x'],p['y']) for p in bounding_box['vertices'] ]
                box_points = np.array(box_points)
            except:
                continue
        
            mask = np.zeros((image.shape[0], image.shape[1]))
            cv2.fillConvexPoly(mask, box_points, (255, 255, 255))
            if check_for_intersections:
                word_objects[x]['polymask'] = mask
        
            avg = np.sum(frame_threshed[mask==255])/255.0
            mask_area = np.sum(mask)/255.0
            
            if avg>hili_to_word_ratio*mask_area:
                #check if the mask intersects with other masks
                if check_for_intersections:
                    intersect_flag=False
                    for y in selected_obj:
                        if abs(x-y)==1 or abs(x-y)>15:
                            continue
                        res, swap = swap_on_intersect(mask, word_objects[y]['polymask'], threshold=0.2)
                        if res:
                            intersect_flag=True
                            if len(word_objects[y]['description'])<len(word_objects[x]['description']):
                                word_objects[y]['description'] = word_objects[x]['description'] 
                            break
                    if intersect_flag:
                        continue
       
                word_objects[x]['sel'] = True
                selected_obj.append(x)
                look_back = max(x-word_sel_thres,0)
                if word_objects[look_back]['sel']:
                    for i in range(look_back+1,x):
                        if not word_objects[i]['sel']:
                            word_objects[i]['sel']=True
                            selected_obj.append(i)
                
        #second round to
        for obj in word_objects:
            try:
                if obj['sel']:
                    bounding_box = obj['boundingPoly']
                    box_points = [(p['x'],p['y']) for p in bounding_box['vertices'] ]
                    box_points = np.array(box_points)
                    hili_text.append(obj['description'])
                    cv2.drawContours(image, [box_points], 0, (0, 0, 50), 1)
            except:
                continue

        if len(hili_text)==0:
            continue        
        contoured_img = "poc_"+os.path.basename(img_path).split(".")[0]+".png"
        all_contoured_imgs.append(contoured_img)
        cv2.imwrite(main_path+"static/uploads/"+contoured_img,image)
        
        ocr_text = [hili_text[0]]
        for w in hili_text[1:]:
            if w not in ['?','.',',',':',';','(',')',"'",'"',"-","_"]:
                ocr_text.append(" "+w)
            else:
                ocr_text.append(w)
        
        all_ocr_text.append("".join(ocr_text))
    return all_ocr_text, all_contoured_imgs

def create_en_resource(file_list):
    resource_list = []
    for filename in file_list:
        # Calculate the md5 hash of the pdf
        md5 = hashlib.md5()
        with open(filename, "rb") as imageFile:
            file_bytes = imageFile.read()
        md5.update(file_bytes)
        md5hash = md5.hexdigest()

        # Create the Data type for evernote that goes into a resource
        file_data = Types.Data()
        file_data.bodyHash = md5hash
        file_data.size = len(file_bytes)
        file_data.body = file_bytes

        # Create a resource for the note that contains the pdf
        file_resource = Types.Resource()
        file_resource.data = file_data
        file_resource.mime = "image/jpg"

        # Create a resource list to hold the pdf resource
        resource_list.append(file_resource)
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
    nBody += "<en-note>%s" % noteBody.replace("\n","<br />")
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

# def remove_gibberish(text):
    
#     from nltk.corpus import words
    
#     test = text.split(" ")
#     # final = []
#     start=0
#     end=len(test)
#     for i in range(len(test)):
#         x = test[i]
#         if x in words.words() or x.isdigit():
#             start=i
#             break

#     for i in range(len(test)-1,-1,-1):
#         x = test[i]
#         if x in words.words() or x.isdigit():
#             end=i
#             break

#     return " ".join(test[start:end+1])

def get_all_text(gcloud_data):
    # Returns a Text Array of the OCR data going throught the Gcloud Vision API Response"""
    all_texts = []
    for textAnnotations in gcloud_data['responses']:
        text_raw = textAnnotations['fullTextAnnotation']['text'].encode('ascii','ignore')
        text = text_raw.replace("\n", " ")
        # text_cleaned = remove_gibberish(text)
        
        all_texts.append(text.strip())

    return all_texts

def create_note_from_highlight(authToken,image_files, note_content, ocr=False, notetitle=''):
    from time import gmtime, strftime

    if notetitle=='':
        curr_time = strftime("%Y-%m-%d", gmtime())
        notetitle="digilight {curr_time}".format(curr_time=curr_time)
    
    if ocr:
        all_texts=[]
        for image_file in image_files:
            json_data, text =google_ocr_img(image_file)
            all_texts.append(text)

        note_content = "\n---------------------\n".join(all_texts)
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
        resources = create_en_resource(image_files)
    except Exception as e:
        return "ERROR: Couldnt make evernote resource.", note_content, str(eobject)
    try:
        note = makeNote(authToken, noteStore, notetitle, note_content,
                 parentNotebook=parentNotebook, resources=resources)
    except Exception as e:
        return "ERROR: Couldnt make evernote.", note_content, str(e)
    
    msg = note.title + " created in " + parentNotebook.name + "!"
    return msg, note_content

if __name__ == '__main__':
    img_path = "sample_images/highlight-sample.jpg"
    c = contour_img(img_path, thresh=100, std_dev=7, hsv_lower=[22, 30, 30], hsv_upper=[45, 255, 255])
    print "Done PRE Contouring:",c
    
    json_data =google_ocr_img([img_path])
    print "API CALL # of responses:", len(json_data['responses'])
    
    list_of_word_obj = get_word_objs(json_data)
    print "# of Word Objects:", len(list_of_word_obj)
    
    all_ocr_text, contoured_imgs = get_post_ocr_contour_text(
        [img_path], 
        list_of_word_obj,
        word_sel_thres = 5, 
        hili_to_word_ratio=0.5)
    
    ocr_text = "\n---------------------\n".join(all_ocr_text)
    
    print "FINAL OCR test after POST Contouring:"
    print ocr_text
