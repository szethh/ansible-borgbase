#!/usr/bin/python

from pprint import pprint

ANSIBLE_METADATA = {
		'metadata_version': '1.1',
		'status': ['preview'],
		'supported_by': 'community'
}

DOCUMENTATION = '''
---
module: borgbase_ssh

short_description: Module for managing SSH keys in borgbase.

version_added: "2.4"

description:
		- "Module for managing SSH keys in borgbase."

options:
		email:
				description:
						- The email address associated with the borgbase account.
				required: true
		password:
				description:
						- The password for the borgbase account.
				required: true
		state:
				description:
						- 'present' to ensure the key exists, 'absent' to ensure it doesn't. When removing key
						match is carried out based on key name only. When adding key, if a key exists with the
						same name but different content, the key will be silently replaced.
				default: present
				choices: [ absent, present ]
		name:
				description:
						- The SSH key name.
				required: true
		key:
				description:
						- The SSH public key (required if state is 'present').
				required: false

author:
		- Andy Hawkins (@adhawkinsgh)
'''

EXAMPLES = '''
- name: Read key from file
  slurp:
    src: ~/.ssh/id_rsa.pub
  register: ssh_key
  check_mode: yes

- name: Create key
  borgbase_ssh:
    state: present
    email: "{{ borgbase_email }}"
    password: "{{ borgbase_password }}"
    name: "{{ whoami.stdout }}@{{ ansible_hostname }}"
    key: "{{ ssh_key['content'] | b64decode }}"
  register: borgbase_key

- name: Dump create results
  debug:
    var: borgbase_key.key_id
'''

RETURN = '''
key_id:
		description: The ID of the key that was created or deleted
		type: int
		returned: always
'''

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.borgbase_client import BorgBaseClient

client = BorgBaseClient()

def login(email, password):
	loginResult=dict(
			success=True,
			errors=[]
		)

	res = client.login(email=email, password=password)
	if 'errors' in res:
		loginResult['success']=False
		for error in res['errors']:
			loginResult['errors'].append(error['message'])

	return loginResult

def readKeys():
	readResult=dict(
			success=True,
			errors=[],
			keys=[]
		)

	keys = client.execute(BorgBaseClient.SSH_LIST)
	if 'errors' in keys:
		readResult['success']=False
		for error in keys['errors']:
			readResult['errors'].append(error['message'])
	else:
		for key in keys['data']['sshList']:
			readResult['keys'].append(key)

	return readResult

def addKey(name, key):
	addResult=dict(
			success=True,
			errors=[]
		)

	key = client.execute(BorgBaseClient.SSH_ADD, dict(name=name, keyData=key))

	if 'errors' in key:
		addResult['success']=False
		for error in key['errors']:
			addResult['errors'].append(error['message'])
	else:
		addResult['keyID']=key['data']['sshAdd']['keyAdded']['id']

	return addResult

def deleteKey(id):
	deleteResult=dict(
			success=True,
			errors=[]
		)

	result = client.execute(BorgBaseClient.SSH_DELETE, dict(id=id))
	if 'errors' in result:
		deleteResult['success']=False
		for error in result['errors']:
			deleteResult['errors'].append(error['message'])

	return deleteResult

def findKey(keys, name):
	for key in keys:
		if name ==key['name']:
			return key

	return None

def runModule():
		# define available arguments/parameters a user can pass to the module
		module_args = dict(
				email=dict(type='str', required=True),
				password=dict(type='str', required=True, no_log=True),
				state=dict(type='str', required=False, choices=['absent', 'present'], default='present'),
				name=dict(type='str', required=True),
				key=dict(type='str', required=False)
		)

		required_if = [
			[ 'state', 'present', ['key']],
		]

		# seed the result dict in the object
		# we primarily care about changed and state
		# change is if this module effectively modified the target
		# state will include any data that you want your module to pass back
		# for consumption, for example, in a subsequent task
		result = dict(
				changed=False,
		)

		# the AnsibleModule object will be our abstraction working with Ansible
		# this includes instantiation, a couple of common attr would be the
		# args/params passed to the execution, as well as if the module
		# supports check mode
		module = AnsibleModule(
				argument_spec=module_args,
				supports_check_mode=True,
				required_if=required_if
		)

		stateExists= module.params['state']=='present'
		# Get a list of keys in the account

		loginResult = login(module.params['email'], module.params['password'])
		if loginResult['success']:
			keys = readKeys()

			if keys['success']:
				foundKey = findKey(keys['keys'], module.params['name'])
				keyExists = foundKey != None
				if keyExists:
					result['key_id']=int(foundKey['id'])


				deleteRequired=False
				addRequired=False

				if keyExists and stateExists:
					if module.params['key'].strip()!=foundKey['keyData']:
						deleteRequired=True
						addRequired=True

				if keyExists and not stateExists:
					deleteRequired=True

				if not keyExists and stateExists:
					addRequired=True

				result['changed']=addRequired or deleteRequired

				if not module.check_mode:
					if deleteRequired:
						deleteResult = deleteKey(int(foundKey['id']))
						if not deleteResult['success']:
							result['msg']=''

							for error in deleteResult['errors']:
								result['msg']+=error

							module.fail_json(**result)

					if addRequired:
						addResult = addKey(module.params['name'], module.params['key'])
						if addResult['success']:
							result['key_id']=addResult['keyID']
						else:
							result['msg']=''

							for error in addResult['errors']:
								result['msg']+=error

							module.fail_json(**result)
			else:
				result['msg']=''

				for error in keys['errors']:
					result['msg']+=error

				module.fail_json(**result)
		else:
			result['msg']=''

			for error in loginResult['errors']:
				result['msg']+=error

			module.fail_json(**result)

		module.exit_json(**result)

def main():
	runModule()

if __name__ == '__main__':
		main()
