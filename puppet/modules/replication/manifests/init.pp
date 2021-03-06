#
# Copyright (C) 2016 Red Hat
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

class replication {
  require gerrituser

  $gerrit_local_key = hiera('creds_gerrit_local_sshkey')

  ssh_authorized_key { 'gerrit_local_user':
    user    => 'gerrit',
    type    => 'ssh-rsa',
    key     => $gerrit_local_key,
    require => File['/home/gerrit/.ssh'],
  }
}
