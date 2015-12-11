# -*- coding: utf-8 -*-
#
# PLUCS (XMPP integration for UCS)
"""PLUCS GROUPS listener module."""
#
# Copyright 2013-2014 it25 GmbH
#
# http://www.it25.de/
#
# All rights reserved.
#
# The source code of this program is made available
# under the terms of the GNU Affero General Public License version 3
# (GNU AGPL V3) as published by the Free Software Foundation.
#
# In the case you use this program under the terms of the GNU AGPL V3,
# the program is provided in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public
# License with the Debian GNU/Linux or Univention distribution in file
# /usr/share/common-licenses/AGPL-3; if not, see
# <http://www.gnu.org/licenses/>.

# pylint: disable-msg=C0103,W0704

__package__ = ''	# workaround for PEP 366
import listener
import univention.debug as ud
import os
import io
import re
import marshal

name = 'plucs-groups'
description = 'Converts group lists into eJabberD ACLs, and group properties to eJabberD access rules.'

filter = '(|(objectClass=univentionXMPPGroup)(objectClass=univentionXMPPAccount))'
attributes = ['cn','memberUid','uid','xmppEnabled','xmppMessageGroups','xmppPresenceGroups']

# set to true for every change
changed = False

# track 'need-to-be-initialized' (read cache needed)
initialized = False

# set on clean(), cleared on first save_data()
cleaned = False

# static storage of groups and users currently known
_dumpfile = os.path.join('/var','cache','plucs',name + '.cache')

_cache = {
	'groups':	{},		# key=group name (sanitized), value=array of member uids
	'gname':	{},		# key=group name (sanitized), value=real group name
	'users':	[],		# uids of all XMPP-enabled users
	'r_mesg':	{},		# key=group name (sanitized), value=array of san. group names (groups to talk to)
	'r_pres':	{}		# key=group name (sanitized), value=array of san. group names (groups to see presence)
	}

def initialize():
	"""Initialize the module once on first start or after clean."""
	
	ud.debug(ud.LISTENER, ud.INFO, 'plucs-groups: initialize() called')
	global initialized
	
	if _read_saved_data():
		_write_groups_config()
		_write_rights_config()
	
	ud.debug(ud.LISTENER, ud.PROCESS, 'plucs-groups: initialized')
	
	initialized = True

def handler(dn, new, old):
	"""Handle changes to 'dn'."""
	global initialized
	global changed
	
	ud.debug(ud.LISTENER, ud.INFO, "plucs-groups: DN '%s' changed" % dn)

	if (not initialized):
		ud.debug(ud.LISTENER, ud.PROCESS, "plucs-groups: initializing on first invocation.")
		initialize()
	
	
	# handle changes to users
	if (dn[0:4] == 'uid='):
		# user appeared or changed?
		if (new):
			enab = (new.get('xmppEnabled')[0] == 'TRUE')
			uid = new.get('uid')[0]

			if enab:
				_add_user(uid)
			else:
				_del_user(uid)

		# user removed?
		else:
			uid = old.get('uid')[0]
			_del_user(uid)
		
		changed = True

	# handle changes to groups
	elif (dn[0:3] == 'cn='):
		
		# modified groups are always removed and readded, this covers all kinds
		# of change (modrdn, xmppEnabled, members, permission lists).
		enab = False
		if (old):
			grpn = _sane_groupname(old.get('cn')[0])
			_del_group(grpn)
			
		if (new):
			gn = new.get('cn')[0]
			grpn = _sane_groupname(gn)
			enab = (new.get('xmppEnabled')[0] == 'TRUE')
			if enab:
				r_mesg = map(_sane_groupname,new.get('xmppMessageGroups',[]))
				r_pres = map(_sane_groupname,new.get('xmppPresenceGroups',[]))
				_add_group(grpn,gn,new.get('memberUid'),r_mesg,r_pres)
		
		changed = True
	
	# should never happen
	else:
		ud.debug(ud.LISTENER, ud.WARN,"plucs-groups: don't know how to handle DN '%s'" % dn)

	_write_groups_config()
	_write_rights_config()
	_save_data()
	
def clean():
	"""Handle request to clean-up the module."""
	global _cache
	global cleaned
	
	ud.debug(ud.LISTENER, ud.PROCESS, "plucs-groups: cleanup requested.")
	
	try:
		_cache = {
			'groups':	{},
			'gname':	{},
			'users':	[],
			'r_mesg':	{},
			'r_pres':	{}
		}

		os.unlink(_dumpfile)
		cleaned = True
	except:
		pass

def postrun():
	"""handle changes after at least 15s of no-changes"""
	ud.debug(ud.LISTENER, ud.INFO, "postrun: plucs-groups running")
	
	global changed
	
	if not changed:
		ud.debug(ud.LISTENER, ud.INFO, "plucs-groups: nothing changed, not restarting daemon.")
		return
		
	changed = False

	ud.debug(ud.LISTENER, ud.PROCESS, "plucs-groups: reloading ACLs (%d users, %d groups)" % (len(_cache['users']),len(_cache['groups'].keys())))
	
	# TODO: set UID 0 and run the to-be-found-command to reload ACLs into an Erlang node
	# Currently: reload eJabberd.
	try:
		listener.run('/usr/sbin/invoke-rc.d', ['invoke-rc.d', 'plucs', 'restart'], uid=0)
	except Exception, e:
		ud.debug(ud.ADMIN, ud.WARN, 'The restart of the PLUCS server failed: %s' % str(e))

# --------------- helper functions ------------------

def _write_groups_config():
	"""write our static data into the config file (mod_filter_groups.cfg)"""
	
	fn = '/etc/ejabberd/mod_filter_groups.cfg'
	listener.setuid(0)
	try:
		f = io.open(fn,'w',encoding='utf-8')
		f.write(u"%% ---------------------------------------------------------\n")
		f.write(u"%% Group ACL file for eJabberD (PLUCS) XMPP service\n")
		f.write(u"%% Please don't edit this file by hand, it will be overwritten\n")
		f.write(u"%% by the next change to any XMPP-enabled group/user.\n")
		f.write(u"%% ---------------------------------------------------------\n\n")

		for g in _cache['groups'].keys():
			if g in _cache['groups']:
				utemp = []
				for u in _cache['groups'][g]:
					if u in _cache['users']:
						utemp.append(u)
				if len(utemp):
					f.write(u"%% ------- %s ------\n" % _cache['gname'][g])
					for u in utemp:
						f.write(u"{acl, %s, {user, \"%s\"}}.\n" % (g,u))

	except Exception,e:
		ud.debug(ud.LISTENER,ud.WARN,"Could not write '%s': %s" % (fn,str(e)))

	finally:
		f.close()
		listener.unsetuid()

def _write_rights_config():
	"""write our static data into the config file (mod_filter.cfg)"""

	fn = '/etc/ejabberd/mod_filter.cfg'
	listener.setuid(0)
	try:
		f = io.open(fn,'w',encoding='utf-8')
		f.write(u"%% ---------------------------------------------------------\n")
		f.write(u"%% Access rules file for eJabberD (PLUCS) XMPP service\n")
		f.write(u"%% Please don't edit this file by hand, it will be overwritten\n")
		f.write(u"%% by the next change to any XMPP-enabled group/user.\n")
		f.write(u"%% ---------------------------------------------------------\n\n")
		

		# empty permission lists for all known sender groups
		mesg_dict = {}
		pres_dict = {}
		for g in _cache['groups'].keys():
			pres_dict[g] = []
			mesg_dict[g] = []
			
		for g in _cache['groups'].keys():
			f.write(u"%% Group: '%s' (%s)\n" % (g,_cache['gname'][g]))
			
			# collect 'message' permissions
			if ('r_mesg' in _cache) and (g in _cache['r_mesg']):
				for tg in _cache['r_mesg'][g]:
					if tg in _cache['groups']:
						f.write(u"%%   Message   ->  [%s]\n" % tg)
						mesg_dict[g].append(tg)
					else:
						f.write(u"%%   Message   ->  [%s] (ignored)\n" % tg)
						
			# collect 'presence' permissions
			if ('r_pres' in _cache) and (g in _cache['r_pres']):
				for tg in _cache['r_pres'][g]:
					if tg in _cache['groups']:
						f.write(u"%%   Presence  <-  [%s]\n" % tg)
						pres_dict[tg].append(g)
					else:
						f.write(u"%%   Presence  <-  [%s] (ignored)\n" % tg)
		
		f.write(u"\n{access, mod_filter, [{allow, all}]}.\n\n")
		f.write(_config_tuple(mesg_dict,'mod_filter_message','message_'))
		f.write(_config_tuple(pres_dict,'mod_filter_presence','presence_'))
		
		f.write(u"{access, mod_filter_iq, [{allow, all}]}.\n\n")
		
	except Exception,e:
		ud.debug(ud.LISTENER,ud.WARN,"Could not write '%s': %s" % (fn,str(e)))
	finally:
		f.close()
		listener.unsetuid()
	
# ----------------- users -------------------

def _add_user(uid):
	"""add the given user to our internal list"""

	if not uid in _cache['users']:
		_cache['users'].append(uid)

def _del_user(uid):
	"""remove the given user from our internal list"""
	
	if uid in _cache['users']:
		_cache['users'].remove(uid)

# -------------- groups ----------------------

def _add_group(grp,name,users,mesg,pres):
	"""add (or update / overwrite) a group"""
	global _cache

	_cache['groups'][grp] = users
	_cache['gname'][grp] = name
	if not 'r_mesg' in _cache:
		_cache['r_mesg'] = {}
	_cache['r_mesg'][grp] = mesg
	if not 'r_pres' in _cache:
		_cache['r_pres'] = {}
	_cache['r_pres'][grp] = pres

def _del_group(grp):
	"""remove a group"""
	
	for key in ['groups','gname','r_mesg','r_pres']:
		if key in _cache:
			if grp in _cache[key].keys():
				del _cache[key][grp]

def _sane_groupname(grp):
	"""Sanitize a (possibly UTF-8) group name for use as an Erlang symbol"""
	#g = grp.casefold()		# Python >=3.3 only! 
	g = grp.lower()
	g = re.sub('[^a-z0-9]+','_',g)
	g = g.strip('_')
	return g

# --------------- cache ----------------------
def _read_saved_data():
	"""Read saved arrays _users and _groups into memory"""
	global _cache
	
	# if 'clear()' was called recently -> it is no error if the dump file doesn't exist
	if cleaned:
		if not os.path.exists(_dumpfile):
			return True

	try:
		f = open(_dumpfile,'rb')
		_cache = marshal.load(f)
		f.close()
		ud.debug(ud.LISTENER,ud.PROCESS,"plucs-groups: read %d users, %d groups from cache" % (len(_cache['users']),len(_cache['groups'].keys())))
		return True
			
	except Exception,e:
		ud.debug(ud.LISTENER, ud.WARN,
		"%s: could not read dump file %s: %s" % (name, _dumpfile, str(e)))
		return False

def _save_data():
	"""Saves arrays _users and _groups across restarts"""
	global cleaned

	# ensure alert on nonexistant dump file	on next _read_saved_data()
	cleaned = False
	
	try:
		f = open(_dumpfile,'wb')
		marshal.dump(_cache,f)
		f.close()
		ud.debug(ud.LISTENER,ud.INFO,"plucs-groups: cached %d users, %d groups" % (len(_cache['users']),len(_cache['groups'].keys())))

	except Exception,e:
		ud.debug(ud.LISTENER, ud.ERROR,
		"%s: could not write dump file %s: %s" % (name, _dumpfile, str(e)))
		                                                                
# ---------------------- optimization -----------------

def _config_tuple(dict,name,prefix,pol1='allow',pol2='deny'):
	"""Returns a snippet of Erlang config items, built from the 'dict' dictionary,
	suitable as access rules.
	
		dict dictionary format:
			key = source group name
			value = array of destination group names to be allowed (can be empty)
		
		name:
			the name of the access rule
			
		prefix:
			the string to prepend onto a group name -> name of associated sub-rule
			
		pol1:
			the policy (fallback rule for 'no match') for the first-level
			access rule
			
		pol2:
			the policy (fallback rule for 'no match') for all second-level
			access rules
			
	All group names are already sanitized, we don't refer to any other
	data but the 'dict' passed in.
	"""
	
	result = u"{access, %s, [\n" % name
	other_rules = u""
	
	for src in dict.keys():
		if len(dict[src]):
			result += u"\t{%s%s, %s},\n" % (prefix,src,src)
			rule = u"{access, %s%s, [\n" % (prefix,src)
			for dst in dict[src]:
				rule += u"\t{allow, %s},\n" % dst
			rule += u"\t{%s, all}\n" % pol2
			rule += u"]}.\n"
			other_rules += rule
		else:
			result += u"\t{deny, %s},\n" % src

	result += u"\t{%s, all}\n" % pol1
	result += u"]}.\n"
	
	return (result + other_rules + u"\n")
