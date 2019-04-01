"""
Tool for syncing a file to Google Drive

Usage:
    gdrive_sync.py --config=FILE
    gdrive_sync.py -h | --help

Options:
    -h --help      Show this help message and exit
    -d --debug     Enable debug logging
"""

# TODO:
# 1. Add docstrings for each method
# 2. Implement encapsulation (optional)
# 3. Add unit tests
# 4. Add logging
# X. Obviously this is a really simple script and
#    would need drastic changes to convert it to
#    a tool

from __future__ import print_function
import configparser
from docopt import docopt
import pickle
import gzip
import shutil
import os
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# If modifying these scopes, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/drive.metadata.readonly',
          'https://www.googleapis.com/auth/drive.file'
         ]

CUR_DIR = os.getcwd()
args = docopt(__doc__)
CONFIGS_FILE = args['--config']
configs = configparser.ConfigParser()
configs.read(CONFIGS_FILE)
SECRETS_DIR = configs['default']['secrets_dir']
local_file_path = configs['default']['file_to_backup']
gdrive_backup_dir = configs['default']['gdrive_backup_dir']
compress = ("true" == configs['default']['compress'])


def fetchCredentials():
    os.chdir(SECRETS_DIR)
    creds = None
    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:

            flow = InstalledAppFlow.from_client_secrets_file(
                'gdrive.json', SCOPES)
            creds = flow.run_local_server()
        # Save the credentials for the next run
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    return creds


def getDirId(by_name, service):
    query = "mimeType='application/vnd.google-apps.folder' \
             and name contains '{}'".format(by_name)

    response = service.files().list(q=query,
                                   fields="files(name, id)",
                                   pageToken=None
                                   ).execute()

    files_found=[]
    for file in response.get('files', []):
        files_found.append(file.get('id'))

    if len(files_found) == 0:
        raise ValueError("ERROR: Unable to find any directory with the name '{}' found!".format(by_name))
    elif len(files_found) > 1:
        raise ValueError("ERROR: Multiple directories with the name '{}' found!".format(by_name))

    return files_found[0]


def fileExists(file_name, folder_id, mimetype, service):
    query = "mimeType='{mimetype}' and \
             name contains '{file_name}' and \
             '{folder_id}' in parents".format(mimetype=mimetype,
                                              file_name=file_name,
                                              folder_id=folder_id)
    response = service.files().list(q=query,
                                   fields="files(mimeType, name, id)",
                                   pageToken=None,
                                   #pageSize=900,
                                   ).execute()

    files_found=[]
    for file in response.get('files', []):
        if file.get('mimeType') == mimetype:
            files_found.append(file.get('id'))

    if len(files_found) == 0:
        print('File not found: {}'.format(files_found))
        return False, 0
    elif len(files_found) == 1:
        print('Files found: {}'.format(files_found))
        return True, files_found[0]
    else:
        raise ValueError("ERROR: Muliple files found in the directory '{}'!".format(folder_id))


def main():

    print('Fetching credentials to access drive API')
    creds=fetchCredentials()

    service = build('drive', 'v3', credentials=creds)

    os.chdir(CUR_DIR)
    os.chdir(os.path.dirname(os.path.realpath(__file__)))

    print("Compressing file before upload")
    filename = os.path.basename(local_file_path)+'.gz' \
                                           if compress \
                                           else os.path.basename(local_file_path)

    mimetype = 'application/unknown'
    if compress:
        mimetype = 'application/gzip'
        with open(local_file_path, 'rb') as file_orig:
            with open(filename, 'wb') as file_zip:
                shutil.copyfileobj(file_orig, file_zip)
    else:
        shutil.copy2(local_file_path, filename)

    dir_id=getDirId(gdrive_backup_dir, service)
    print("Folder '{dir}' found with ID: {id}".format(dir=gdrive_backup_dir, id=dir_id))

    file_exists, file_id = fileExists(filename, dir_id, mimetype, service)
    body = {
            'name': filename,
            'parents': [dir_id]
           }


    media = MediaFileUpload(filename, mimetype=mimetype)

    # Call the Drive v3 API
    if not file_exists:
        file = service.files().create(body=body,
                                      media_body=media,
                                      fields='id').execute()
    else:
        file = service.files().update(fileId=file_id,
                                      media_body=media).execute()
    os.remove(filename)
    print('File uploaded successfully!')


if __name__ == '__main__':
    main()
