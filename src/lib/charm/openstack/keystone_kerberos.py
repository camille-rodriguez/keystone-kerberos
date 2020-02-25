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

APACHE_CONF_TEMPLATE = "apache-kerberos.conf"
KERBEROS_CONF_TEMPLATE = "krb5.conf"
KEYTAB_PATH = "/etc/keystone.keytab"

class KeystoneKerberosCharm(
    charms_openstack.charm.OpenStackCharm):

    # Internal name of charm
    service_name = name = 'keystone-kerberos'

    # Package to derive application version from
    version_package = 'keystone'

    # First release supported
    release = 'queens'

    release_pkg = 'keystone-common'

    # Required relations
    required_relations = [
        'keystone-fid-service-provider']

    # List of packages to install for this charm
    packages = ['libapache2-mod-auth-kerb']

    restart_map = {
        APACHE_CONF_TEMPLATE: [],
        KERBEROS_CONF_TEMPLATE: [],
        KEYTAB_PATH: [],
    }

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

    def configuration_complete(self):
        """Determine whether sufficient configuration has been provided
        to configure keystone for use with a Kerberos server

        :returns: boolean indicating whether configuration is complete
        """
        required_config = {
            'kerberos_realm': self.options.kerberos-realm,
            'kerberos_server': self.options.kerberos-server,
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
        """
        Render Kerberos configuration file and Apache configuration to be used
        by Keystone.
        """
        owner = 'root'
        group = 'www-data'
        # using the same parameters as keystone-saml-mellon charm for now
        dperms = 0o650
        fileperms = 0o440
        # ensure that a directory we need is there
        ch_host.mkdir('/etc/apache2/kerberos', perms=dperms, owner=owner,
                      group=group)

        self.render_configs(self.string_templates.keys())

        core.templating.render(
            source=APACHE_CONF_TEMPLATE,
            template_loader=os_templating.get_loader(
                'templates/', self.release),
            target='/etc/apache2/kerberos/{}'.format(APACHE_CONF_TEMPLATE),
            context=self.adapters_instance,
            owner=owner,
            group=group,
            perms=fileperms
        )

        core.templating.render(
            source=KERBEROS_CONF_TEMPLATE,
            template_loader=os_templating.get_loader(
                'templates/', self.release),
            target="/etc/krb5.conf",
            context=self.adapters_instance
        )


    def remove_config(self):
        for f in self.restart_map.keys():
            if os.path.exists(f):
                os.unlink(f)