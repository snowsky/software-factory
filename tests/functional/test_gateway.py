#!/bin/env python
#
# Copyright (C) 2014 eNovance SAS <licensing@enovance.com>
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import re

import config
from utils import Base
from utils import ManageSfUtils
from utils import skipIfIssueTrackerMissing, has_issue_tracker, \
    skipIfServiceMissing
from utils import get_issue_tracker_utils
from pysflib.sfgerrit import GerritUtils

from requests.auth import HTTPBasicAuth
from requests.exceptions import HTTPError

import requests


class TestGateway(Base):
    def _auth_required(self, url):
        resp = requests.get(url, allow_redirects=False)
        self.assertEqual(resp.status_code, 307)
        self.assertTrue("/auth/login" in resp.headers['Location'])

    @skipIfIssueTrackerMissing()
    def test_tracker_root_url_for_404(self):
        """ Test if tracker yield RoutingError
        """
        tracker = get_issue_tracker_utils(
            auth_cookie=config.USERS[config.ADMIN_USER]['auth_cookie'])
        url = tracker.get_root_url()
        for i in xrange(11):
            resp = requests.get(url)
            self.assertNotEquals(resp.status_code, 404,
                                 "%s returned status %s" % (url,
                                                            resp.status_code))

    @skipIfServiceMissing('SFRedmine')
    def test_redmine_versions_edit(self):
        tracker = get_issue_tracker_utils()
        cookies = dict(auth_pubtkt=config.USERS[config.USER_1]['auth_cookie'])

        # We need a session, because we execute two requests and the
        # authenticity_token is assigned to a session
        s = requests.Session()

        url = "%s/projects/config/versions/new" % tracker.get_root_url()
        resp = s.get(url, cookies=cookies)

        # Find the authenticity_token in the response
        m = re.search('authenticity_token.*value="(.*)"', resp.text)
        authenticity_token = m.group(1)

        # Create a new version
        url = "%s/projects/config/versions" % tracker.get_root_url()
        data = {'version[name]': 'sample6',
                'authenticity_token': authenticity_token}
        resp = s.post(url, data, cookies=cookies)
        self.assertEqual(resp.status_code, 200)

        # Edit the version
        url = "%s/versions/1" % tracker.get_root_url()
        data = {'version[name]': 'sample20',
                'authenticity_token': authenticity_token,
                '_method': 'put'}
        resp = s.post(url, data, cookies=cookies, allow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        location = resp.headers.get('Location')
        self.assertEqual(
            location,
            '%s/projects/config/settings/versions' % tracker.get_root_url())

    def _url_is_not_world_readable(self, url):
        """Utility function to make sure a url is not accessible"""
        resp = requests.get(url)
        self.assertTrue(resp.status_code > 399, resp.status_code)

    def test_managesf_is_secure(self):
        """Test if managesf config.py file is not world readable"""
        url = "%s/managesf/config.py" % config.GATEWAY_URL
        self._url_is_not_world_readable(url)

    def test_cauth_is_secure(self):
        """Test if managesf config.py file is not world readable"""
        url = "%s/cauth/config.py" % config.GATEWAY_URL
        self._url_is_not_world_readable(url)

    # TODO(XXX) this is not up to date and can change with config
    def test_topmenu_links_shown(self):
        """ Test if all service links are shown in topmenu
        """
        subpaths = ["/r/", "/jenkins/",
                    "/zuul/", "/etherpad/", "/paste/", "/docs/"]
        if has_issue_tracker():
            tracker = get_issue_tracker_utils(
                auth_cookie=config.USERS[config.ADMIN_USER]['auth_cookie'])
            if 'redmine' in tracker.get_root_url():
                subpaths.append('/%s/' % 'redmine')
        url = config.GATEWAY_URL + "/topmenu.html"
        resp = requests.get(url)
        self.assertEqual(resp.status_code, 200)
        for subpath in subpaths:
            self.assertTrue(('href="%s"' % subpath) in resp.text,
                            '%s not present as a link' % subpath)

    def test_gerrit_accessible(self):
        """ Test if Gerrit is accessible on gateway hosts
        """
        # Unauthenticated calls
        urls = [config.GATEWAY_URL + "/r/",
                config.GATEWAY_URL + "/r/#/"]

        for url in urls:
            resp = requests.get(url)
            self.assertEqual(resp.status_code, 200)
            self.assertTrue('<title>Gerrit Code Review</title>' in resp.text)

        # URL that requires login - shows login page
        url = config.GATEWAY_URL + "/r/a/projects/?"
        resp = requests.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue('form-signin' in resp.text)

        # Authenticated URL that requires login
        url = config.GATEWAY_URL + "/r/a/projects/?"
        self._auth_required(url)
        resp = requests.get(
            url,
            cookies=dict(
                auth_pubtkt=config.USERS[config.USER_1]['auth_cookie']))
        self.assertEqual(resp.status_code, 200)
        # /r/a/projects returns JSON list of projects
        self.assertTrue('All-Users' in resp.text)

    def test_gerrit_projectnames(self):
        """ Test if projectnames similar to LocationMatch settings work
        """
        # Unauthenticated calls, unknown projects. Must return 404, not 30x
        urls = [config.GATEWAY_URL + "/r/dashboard",
                config.GATEWAY_URL + "/r/grafana",
                config.GATEWAY_URL + "/r/jenkinslogs"]

        for url in urls:
            resp = requests.get(url, allow_redirects=False)
            self.assertEqual(resp.status_code, 404)

    def test_gerrit_api_accessible(self):
        """ Test if Gerrit API is accessible on gateway hosts
        """
        m = ManageSfUtils(config.GATEWAY_URL)
        url = config.GATEWAY_URL + "/api/"

        a = GerritUtils(url)
        a.g.url = "%s/" % a.g.url.rstrip('a/')
        self.assertRaises(HTTPError, a.get_account, config.USER_1)

        api_passwd = m.create_gerrit_api_password(config.USER_1)
        auth = HTTPBasicAuth(config.USER_1, api_passwd)
        a = GerritUtils(url, auth=auth)
        self.assertTrue(a.get_account(config.USER_1))

        m.delete_gerrit_api_password(config.USER_1)
        a = GerritUtils(url, auth=auth)
        self.assertRaises(HTTPError, a.get_account, config.USER_1)

        a = GerritUtils(url)
        a.g.url = "%s/" % a.g.url.rstrip('a/')
        self.assertRaises(HTTPError, a.get_account, 'john')

    def test_jenkins_accessible(self):
        """ Test if Jenkins is accessible on gateway host
        """
        url = config.GATEWAY_URL + "/jenkins/"

        # Without SSO cookie. Note that auth is no longer enforced

        resp = requests.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue('<title>Dashboard [Jenkins]</title>' in resp.text)

        # With SSO cookie
        resp = requests.get(
            url, cookies=dict(
                auth_pubtkt=config.USERS[config.USER_1]['auth_cookie']))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue('<title>Dashboard [Jenkins]</title>' in resp.text)

        # User should be known in Jenkins if logged in with SSO
        self.assertTrue(config.USER_1 in resp.text)

    def test_zuul_accessible(self):
        """ Test if Zuul is accessible on gateway host
        """
        url = config.GATEWAY_URL + "/zuul/"
        resp = requests.get(
            url,
            cookies=dict(
                auth_pubtkt=config.USERS[config.USER_1]['auth_cookie']))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue('<title>Zuul Status</title>' in resp.text)

    @skipIfIssueTrackerMissing()
    def test_tracker_accessible(self):
        """ Test if Issue Tracker is accessible on gateway host
        """
        tracker = get_issue_tracker_utils(
            auth_cookie=config.USERS[config.ADMIN_USER]['auth_cookie'])
        url = tracker.get_root_url()

        # Without SSO cookie. Note that auth is no longer enforced
        resp = requests.get(url)
        self.assertEqual(resp.status_code, 200,
                         "%s returned status %s" % (url, resp.status_code))

        # With SSO cookie
        resp = requests.get(
            url,
            cookies=dict(
                auth_pubtkt=config.USERS[config.USER_1]['auth_cookie']))
        self.assertEqual(resp.status_code, 200)

        # User should be known in tracker if logged in with SSO
        self.assertTrue(config.USER_1 in resp.text)

        # Check one of the static files is accessible
        url = tracker.test_static_file()
        resp = requests.get(
            url,
            cookies=dict(
                auth_pubtkt=config.USERS[config.USER_1]['auth_cookie']))
        self.assertEqual(resp.status_code, 200,
                         "%s returned status %s" % (url, resp.status_code))

    def test_etherpad_accessible(self):
        """ Test if Etherpad is accessible on gateway host
        """
        url = config.GATEWAY_URL + "/etherpad/"
        resp = requests.get(
            url,
            cookies=dict(
                auth_pubtkt=config.USERS[config.USER_1]['auth_cookie']))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue('<title>SF - Etherpad</title>' in resp.text)

    def test_paste_accessible(self):
        """ Test if Paste is accessible on gateway host
        """
        url = config.GATEWAY_URL + "/paste/"
        resp = requests.get(
            url,
            cookies=dict(
                auth_pubtkt=config.USERS[config.USER_1]['auth_cookie']))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue('<title>New Paste | LodgeIt!</title>' in resp.text)

    def test_css_js_for_topmenu_accessible(self):
        """ Test if css/js for topmenu are accessible on gateway host
        """
        url = config.GATEWAY_URL + "/static/js/jquery.min.js"
        resp = requests.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue("jQuery v2.1.1" in resp.content)

        paths = ('js/bootstrap.min.js', 'css/bootstrap.min.css')
        for p in paths:
            url = config.GATEWAY_URL + "/static/bootstrap/%s" % p
            resp = requests.get(url)
            self.assertEqual(resp.status_code, 200)
            self.assertTrue("Bootstrap v3.2.0" in resp.content)

    def test_static_dir_for_paste_accessible(self):
        """ Test if static dir for paste is accessible on gateway host
        """
        url = config.GATEWAY_URL + "/static/lodgeit/jquery.js"
        resp = requests.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue("jQuery 1.2.6" in resp.content)

    def test_docs_accessible(self):
        """ Test if Sphinx docs are accessible on gateway host
        """
        url = config.GATEWAY_URL + "/docs/index.html"
        resp = requests.get(url)
        self.assertEqual(resp.status_code, 200)

    def test_dashboard_accessible(self):
        """ Test if Dashboard is accessible on gateway host
        """
        url = config.GATEWAY_URL + "/dashboard/"

        self._auth_required(url)

        resp = requests.get(
            url,
            cookies=dict(
                auth_pubtkt=config.USERS[config.USER_1]['auth_cookie']))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue('<body ng-controller="mainController">' in resp.text)

    def test_jenkinslogs_accessible(self):
        """ Test if Jenkins logs are accessible on gateway host
        """
        url = "http://%s/jenkinslogs/127.0.0.1/dashboard/" % (
            config.GATEWAY_HOST)
        resp = requests.get(url, allow_redirects=False)
        self.assertEqual(resp.status_code, 307)

        self._auth_required(url)

        resp = requests.get(
            url,
            cookies=dict(
                auth_pubtkt=config.USERS[config.USER_1]['auth_cookie']))
        self.assertEqual(resp.status_code, 200)

        url = "http://%s/jenkinslogs/127.0.0.2/dashboard/" % (
            config.GATEWAY_HOST)
        resp = requests.get(
            url,
            cookies=dict(
                auth_pubtkt=config.USERS[config.USER_1]['auth_cookie']))
        self.assertEqual(resp.status_code, 404)
