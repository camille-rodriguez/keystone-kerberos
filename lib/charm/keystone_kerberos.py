from charms.reactive import when, when_not, set_flag
import charmhelpers.core as core
import charmhelpers.core.host as ch_host
import charmhelpers.core.hookenv as hookenv

import charmhelpers.contrib.openstack.templating as os_templating
import charmhelpers.contrib.openstack.utils as os_utils

import charms_openstack.charm
import charms_openstack.adapters

import os
import shutil

KERBEROS_CONF_TEMPLATE = "kerberos.conf"
KEYTAB_PATH = "/etc/keystone.keytab"

class KeystoneKerberosCharm(
    charms_openstack.charm.OpenStackCharm):

    # Internal name of charm
    service_name = name = 'keystone-kerberos'

    # Package to derive application version from
    version_package = 'keystone'

    # First release supported
    release = 'queens'

    # List of packages to install for this charm
    packages = ['libapache2-mod-auth-kerb']

    @property
    def kerberos_realm(self):
        """Realm name for the running application

        :returns: string: containing the realm name for the application
        """
        return hookenv.config('kerberos-realm')

    def kerberos_server(self):
        """Server name for the running application

        :returns: string: containing the server name for the application
        """
        return hookenv.config('kerberos-server')

    @staticmethod
    def configuration_complete():
        """Determine whether sufficient configuration has been provided
        to configure keystone for use with a Kerberos server

        :returns: boolean indicating whether configuration is complete
        """
        required_config = {
            'kerberos_realm': hookenv.config('kerberos-realm'),
            'kerberos_server': hookenv.config('kerberos-server'),
        }
        return all(required_config.values())

    @property
    def kerb_conf_path(self):
        return '/kerberos'

    @property
    def keytab_path(self):
        """Path for they keytab file"""
        keytab_file = hookenv.resource_get('keystone_keytab')
        shutil.copy(keytab_file, KEYTAB_PATH)
        return KEYTAB_PATH

    def assess_status(self):
        """Determine the current application status for the charm"""
        if not self.configuration_complete():
            hookenv.status_set('blocked',
                               'Kerberos configuration incomplete')
        elif os_utils.is_unit_upgrading_set():
            hookenv.status_set('blocked',
                               'Ready for do-release-upgrade and reboot. '
                               'Set complete when finished.')
        else:
            hookenv.status_set('active',
                               'Unit is ready')

    def render_config(self, restart_trigger):
        checksum = ch_host.file_hash(self.configuration_file)
        core.templating.render(
            source=KERBEROS_CONF_TEMPLATE,
            template_loader=os_templating.get_loader(
                'templates/', self.release),
            target='/etc/apache2/kerberos/'.format(KERBEROS_CONF_TEMPLATE),
            context=self.adapters_instance)
        tmpl_changed = (checksum !=
                        ch_host.file_hash(self.configuration_file))
        #Could add a check if kerberos info changed, if so, restart trigger
        if tmpl_changed:
            restart_trigger()

    def remove_config(self):
        """
        Remove the kerberos configuration file and trigger
        keystone restart.
        """
        if os.path.exists(self.configuration_file):
            os.unlink(self.configuration_file)
