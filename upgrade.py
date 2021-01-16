from cvprac.cvp_client import CvpClient
import os
import sys
import time

"""
Upload the latest EOS image as provided on the command line, located in the current directory
   
    python upgrade.py EOS-4.24.4M.swi 42

Change the EOS-latest image bundle to include this new image.
TODO: support TerminAttr and ocprometheus
TODO: support ccid generation (https://github.com/aristanetworks/cvprac/issues/132). We provide the ccid on the commandine for the time being.
TODO: download the EOS image by itself
"""

clnt = CvpClient()
clnt.connect([os.environ['CVP_HOST']], 'cvpadmin', os.environ['CVP_PASS'])
latestbundle = clnt.api.get_image_bundle_by_name('EOS-latest')

# we extract the images in there and upgrade the EOS one
EOS = list(filter(lambda x: x['imageFileName'].startswith('EOS'), latestbundle['images']))[0]
notEOS = list(filter(lambda x: not x['imageFileName'].startswith('EOS'), latestbundle['images']))

print ("currentlatest: ", EOS['name'])
if len(sys.argv) < 2 or not sys.argv[1].startswith('EOS'):
    print ("no image provided")
    sys.exit(0)


if (sys.argv[1] == EOS['name']):
    # bundle already contains the image
    print ("skip image upload")
else:
    # check if EOS image needs an upload
    allImages = clnt.api.get_images()
    imageToUse = list(filter(lambda x: x['name'] == sys.argv[1], allImages['data']))
    if len(imageToUse) > 0:
        # image was there already
        print("we will use", imageToUse)
    else:
        # upload the image
        print("uploading new EOS")
        resp = clnt.api.add_image(sys.argv[1])
        # image should be there now
        allImages = clnt.api.get_images()
        imageToUse = list(filter(lambda x: x['name'] == sys.argv[1], allImages['data']))
    
    # construct the bundle with the new EOS image, keeping the rest as-is
    images = list(notEOS) + imageToUse
    print ("uploading", latestbundle['id'], latestbundle['name'], images, latestbundle['isCertifiedImage'] == "true")
    resp = clnt.api.update_image_bundle(latestbundle['id'], latestbundle['name'], images, latestbundle['isCertifiedImage'])
    print(resp)

# find any pending task to execute
tasks = []
for task in clnt.api.change_control_available_tasks():
    if task['data']['imagebundle']['name']  == "EOS-latest":
        tasks = tasks + [ task['workOrderId'] ]

if len(tasks) == 0:
    print ("no task to execute")
    sys.exit(0)

# create and execute the change control
# TODO: generate a ccid
if len(sys.argv) < 3:
    print ("ccid to be provided in argument. See https://github.com/aristanetworks/cvprac/issues/132")
    sys.exit(-1)

ccid=sys.argv[2]
cc = clnt.api.create_change_control_v3(ccid, "EOS-latest to "  + sys.argv[1], tasks)
ccid=cc[0]['id']
res=clnt.api.approve_change_control(ccid, cc[0]['update_timestamp'])
res=clnt.api.execute_change_controls([ccid])


