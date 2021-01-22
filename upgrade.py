from cvprac.cvp_client import CvpClient
import os
import sys
import time
import feedparser
import re

"""
Upload the latest EOS image as provided on the command line, located in the current directory
   
    python upgrade.py 42

Change the EOS-latest image bundle to include this new image.
TODO: support TerminAttr and ocprometheus
TODO: support ccid generation (https://github.com/aristanetworks/cvprac/issues/132). We provide the ccid on the commandine for the time being.
TODO: some precheck, validation, and alert silencing
"""

def extractReleases():
    """
    Extract all recent releases of EOS
    """
    URL = "https://www.arista.com/support/release-notes"
    d = feedparser.parse(URL)
    releases = []
    for e in d.entries:
        m = re.match(r"https://www\.arista\.com/support/releasenotes/RN([\d\.-]+M).*", e.link)
        if m:
            releases += [ m.group(1) ]
    return releases
           
def findTargetVersion(current, releases):
    """
    Given a current image EOS-X.Y, retrieve the latest X.Y.Z version released.
    """
    m = re.match(r"^EOS-(\d*\.\d*)\.([\d\.-]+M).swi", current)
    assert (m)
    for r in releases:
        if r.startswith(m.group(1)):
            return r
    return None
        
def eos_download(targetversion, targetimage, apikey):
    """
    Use Arista provided script from https://github.com/arista-netdevops-community/eos-scripts
    TODO Migrate to CVP API when it supports it
    """
    rc = os.system("python eos_download.py --api %s --ver %s" % (apikey, targetversion))
    assert (rc == 0)
    assert (os.path.isfile(targetimage))
    return True
    
def precheck():
    pass    
    
    
clnt = CvpClient()
clnt.connect([os.environ['CVP_HOST']], 'cvpadmin', os.environ['CVP_PASS'])
latestbundle = clnt.api.get_image_bundle_by_name('EOS-latest')

# we extract the images in there and upgrade the EOS one
EOS = list(filter(lambda x: x['imageFileName'].startswith('EOS'), latestbundle['images']))[0]
notEOS = list(filter(lambda x: not x['imageFileName'].startswith('EOS'), latestbundle['images']))

print ("currentlatest: ", EOS['name'])
targetRelease = findTargetVersion(EOS['name'], extractReleases())

if not targetRelease:
    print ("no target release found")
    sys.exit(0)
else:
    print ("Found target release ", targetRelease)
targetImage = "EOS-" + targetRelease + ".swi"


if (targetImage == EOS['name']):
    # bundle already contains the image
    print ("skip bundle update")
else:
    # check if EOS image needs an upload
    allImages = clnt.api.get_images()
    imageToUse = list(filter(lambda x: x['name'] == targetImage, allImages['data']))
    if len(imageToUse) > 0:
        # image was there already
        print("we will use", imageToUse)
    else:
        # upload the image
        eos_download(targetRelease, targetImage, os.env['ARISTA_KEY'])
        print("uploading new EOS")
        resp = clnt.api.add_image(targetImage)
        # image should be there now
        allImages = clnt.api.get_images()
        imageToUse = list(filter(lambda x: x['name'] == targetImage, allImages['data']))
    
    assert(len(imageToUse) == 1)
    # construct the bundle with the new EOS image, keeping the rest as-is
    images = list(notEOS) + imageToUse
    print ("updating", latestbundle['id'], latestbundle['name'], images, latestbundle['isCertifiedImage'] == "true")
    resp = clnt.api.update_image_bundle(latestbundle['id'], latestbundle['name'], images, latestbundle['isCertifiedImage'] == "true")
    print(resp)

# find any pending task to execute
tasks = []
for task in clnt.api.change_control_available_tasks():
    if task['data']['imagebundle']['name']  == "EOS-latest":
        tasks = tasks + [ task['workOrderId'] ]
    else:
        print ("Found unrelated tasks. Not executing")
        sys.exit(3)

if len(tasks) == 0:
    print ("no task to execute")
    sys.exit(0)

precheck()

# create and execute the change control
# TODO: generate a ccid
if len(sys.argv) < 2:
    print ("ccid to be provided in argument. See https://github.com/aristanetworks/cvprac/issues/132")
    sys.exit(-1)

ccid=sys.argv[1]
cc = clnt.api.create_change_control_v3(ccid, "EOS-latest to "  + targetRelease, tasks)
ccid=cc[0]['id']
res=clnt.api.approve_change_control(ccid, cc[0]['update_timestamp'])
res=clnt.api.execute_change_controls([ccid])


