import json, base64

import requests

import cv2
import numpy as np
with open('/var/www/Digilight/digilight/config.json') as json_data_file:
    data = json.load(json_data_file)
#  Client Keys
GOOGLE_API_KEY = data['google_api_key']


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


def google_ocr_img(img_path):
    cropped_hili_img = "color-contour-crop.jpg"
    image = cv2.imread(img_path)

    # rgb to HSV color spave conversion
    hsv_img = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

    HSV_lower = np.array([22, 50, 50], np.uint8)  # Lower HSV value
    HSV_upper = np.array([30, 250, 250], np.uint8)  # Upper HSV value

    frame_threshed = cv2.inRange(hsv_img, HSV_lower, HSV_upper)
    cv2.imwrite("color-thresh.jpg",frame_threshed)
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

    data = convert_img_to_json([cropped_hili_img+" 7:10"])
    response = requests.post(url="https://vision.googleapis.com/v1/images:annotate?key={key}".format(key=GOOGLE_API_KEY),
        data=data,
        headers={'Content-Type': 'application/json'})

    api_result = response.json()
    return api_result
    