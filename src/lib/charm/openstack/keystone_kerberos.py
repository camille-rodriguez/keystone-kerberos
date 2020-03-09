from charms.reactive import when, when_not, set_flag
import charmhelpers.core as core
import charmhelpers.core.host as ch_host
import charmhelpers.core.hookenv as hookenv

import charmhelpers.contrib.openstack.templating as os_templating
import charmhelpers.contrib.openstack.utils as os_utils

import charms_openstack.charm
import charms_openstack.adapters
# release detection is done via keystone package given that
# openstack-origin is not present in the subordinate charm
# see https://github.com/juju/charm-helpers/issues/83
import charmhelpers.core.unitdata as unitdata
from charms_openstack.charm.core import (
    register_os_release_selector
)

import os
import shutil

OPENSTACK_RELEASE_KEY = 'charmers.openstack-release-version'
APACHE_CONF_TEMPLATE = "apache-kerberos.conf"
APACHE_WSGI_CONF_TEMPLATE = "apache-wsgialias-kerberos.conf"
APACHE_LOCATION = '/etc/apache2/kerberos'
KERBEROS_CONF_TEMPLATE = "krb5.conf"
KEYTAB_PATH = "/etc/keystone.keytab"


@register_os_release_selector
def select_release():
    """Determine the release based on the keystone package version.

    Note that this function caches the release after the first install so
    that it doesn't need to keep going and getting it from the package
    information.
    """
    release_version = unitdata.kv().get(OPENSTACK_RELEASE_KEY, None)
    if release_version is None:
        release_version = os_utils.os_release('keystone')
        unitdata.kv().set(OPENSTACK_RELEASE_KEY, release_version)
    return release_version


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
    def protocol_name(self):
        """Protocol name to be used in the auth methods via f
        id-service-provider interface

        :returns: string: containing the protocol name
        """
        return 'kerberos'

    @property
    def kerberos_realm(self):
        """Realm name for the running application

        :returns: string: containing the realm name for the application
        """
        return hookenv.config('kerberos-realm')

    @property
    def kerberos_server(self):
        """Server name for the running application

        :returns: string: containing the server name for the application
        """
        return hookenv.config('kerberos-server')

    @property
    def kerberos_domain(self):
        """Server name for the running application

        :returns: string: containing the server name for the application
        """
        return hookenv.config('kerberos-domain')

    @staticmethod
    def configuration_complete():
        """Determine whether sufficient configuration has been provided
        to configure keystone for use with a Kerberos server

        :returns: boolean indicating whether configuration is complete
        """
        required_config = {
            'kerberos_realm': hookenv.config('kerberos-realm'),
            'kerberos_server': hookenv.config('kerberos-server'),
            'kerberos_domain': hookenv.config('kerberos-domain'),
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
        ch_host.mkdir(APACHE_LOCATION, perms=dperms, owner=owner,
                      group=group)

        self.render_configs(self.string_templates.keys())

        core.templating.render(
            source=APACHE_CONF_TEMPLATE,
            template_loader=os_templating.get_loader(
                'templates/', self.release),
            target='{}/{}'.format(APACHE_LOCATION, APACHE_CONF_TEMPLATE),
            context=self.adapters_instance,
            owner=owner,
            group=group,
            perms=fileperms
        )

        core.templating.render(
            source=APACHE_WSGI_CONF_TEMPLATE,
            template_loader=os_templating.get_loader(
                'templates/', self.release),
            target='{}/{}'.format(APACHE_LOCATION, APACHE_WSGI_CONF_TEMPLATE),
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
