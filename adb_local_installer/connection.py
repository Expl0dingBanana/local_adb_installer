from adbutils import adb, AdbClient
import apkutils
import logging
import re
from distutils.version import LooseVersion


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
logger.addHandler(ch)

package_manifest = {}


class ADBConnection(object):
    """Connect to the device via ADB

    :ivar str serial: ADB serial used for the connection. This
        will be the connection identifier for the device
    :ivar int retries: Number of retries to be used. Default: 3
    :ivar int timeout: Number of milliseconds to be used for any
        connection issues. Default: 3000
    :ivar bool disconnect: Disconnect from the device when finished

    """
    def __init__(self, host, port=5555, domain=None, retries=3, timeout=3000,
                 disconnect=False):
        if domain:
            serial = "{}.{}:{}".format(host, domain, port)
        else:
            serial = "{}:{}".format(host, port)
        self.serial = serial
        self.retries = retries
        self.timeout = timeout
        self.disconnect = disconnect
        logger.info("Connecting to the ADB server")
        AdbClient()
        logger.info("Connected to the ADB server")
        self.conn = False

    def __enter__(self):
        retries = 0
        while retries < self.retries:
            logger.info("Starting connection to %s", self.serial)
            if "cannot connect to" in adb.connect(self.serial, timeout=self.timeout):
                retries += 1
                logger.warning("Unable to connect to %s [%s/%s]", self.serial, retries, self.retries)
                continue
            self.conn = adb.device(serial=self.serial)
            logger.info("Successfully connected to %s", self.serial)
            break
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.disconnect:
            adb.disconnect(serial=self.serial)

    @staticmethod
    def get_apk_name(apk) -> str:
        """Read the APK and lookup the name

        :param binary apk: APK file

        :return: Package name
        :rtype: str
        """
        return ADBConnection._package_manifest(apk)["@package"]
        return pkg_name

    @staticmethod
    def get_remote_path(name) -> str:
        return "/sdcard/{}".format(name)

    def install_apk(self, local_path: str):
        with open(local_path, "rb") as fh:
            try:
                manifest = ADBConnection._package_manifest(fh)
            except (IOError, OSError) as err:
                logger.warning("Unable to open the file %s", local_path)
                raise err
            fh.seek(0, 0)
            try:
                name: str = ADBConnection.get_apk_name(fh)
            except Exception as err:
                logger.warning("Unable to read package name. Skipping")
                raise err
            fh.seek(0, 0)
            if not self.requires_install(manifest):
                logger.info("Update is not required. Skipping")
                return None
            logger.info("Installation required. Pushing the file")
            remote_path = ADBConnection.get_remote_path(name)
            try:
                # self._push_apk(local_path, remote_path)
                logger.info("File successfully pushed")
                self._install_apk(remote_path)
                logger.info("File successfully installed")
            except Exception as err:
                logger.error(err)
                raise err
            finally:
                logger.info("Removing the file")
                self._remove_apk(remote_path)
            return True

    def _install_apk(self, local_path):
        self.conn.shell(["pm", "install" "-r", local_path])

    @staticmethod
    def _package_manifest(apk):
        global package_manifest
        if apk not in package_manifest:
            package_manifest[apk] = apkutils.APK(apk).get_manifest()
        return package_manifest[apk]

    def _push_apk(self, local_path, remote_path):
        # @TODO - Implement retries
        self.conn.sync.push(local_path, remote_path)

    def _remove_apk(self, remote_path):
        self.conn.shell(["rm", remote_path])

    def requires_install(self, manifest) -> bool:
        apk_ver = manifest["@android:versionName"]
        apk_name = manifest["@package"]
        # @TODO - Implement retries
        version_raw = self.conn.shell(["dumpsys", "package", apk_name, "|", "grep", "versionName"])
        package_ver = re.search(r'versionName=([0-9\.]+)', version_raw).group(1)
        logger.info("Installed: %s; APK: %s", package_ver, apk_ver)
        return LooseVersion(apk_ver) > LooseVersion(package_ver)
