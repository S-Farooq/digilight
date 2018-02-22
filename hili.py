import json, base64, binascii,hashlib
from evernote.api.client import EvernoteClient
import evernote.edam.type.ttypes as Types
import evernote.edam.error.ttypes as Errors

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

image_file = "highlight-sample.jpg"
json_data=open("api_result.json").read()

data = json.loads(json_data)
all_texts = get_all_text(data)

dev_token = "S=s1:U=946af:E=1691629fdb0:C=161be78cfa0:P=1cd:A=en-devtoken:V=2:H=62d05bfbbde1b056b12169ea273b31ce"
client = EvernoteClient(token=dev_token)
userStore = client.get_user_store()
user = userStore.getUser()
print user.username

noteStore = client.get_note_store()
notebooks = noteStore.listNotebooks()
for n in notebooks:
    if n.name=='hilis':
        parentNotebook=n

resources = create_en_resource(image_file)
makeNote(dev_token, noteStore, "Test-HILI", "\n\n".join(all_texts),
         parentNotebook=parentNotebook, resources=resources)

