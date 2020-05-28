"""
@author: Majdoub khalid
I know you are tired of all these 10 thousands test frameworks that take like forever to put in work.
This is an nso A-Z test automation framework.
It will make creating a CI-CD for your NSO services just a piece of cake.
All in one python class !!
"""
import subprocess
import ncs
import difflib
import os
import logging


# m = ncs.maapi.Maapi()
# ncs.maapi.Session(m, 'admin', 'admin')
# t = m.start_write_trans()


def get_log():
    format = '<%(levelname)s line %(lineno)d> %(filename)s %(funcName)s: - %(message)s'
    test_bed = os.path.dirname(os.path.realpath(__file__))
    log_path = os.path.join(test_bed, "pynso.log")
    logging.basicConfig(filename=log_path, level=logging.INFO, format=format)
    log = logging.getLogger('pynso_logger')
    return log


class PyNSO:

    def __init__(self, username='admin', password='admin', log=None, NCS_RUN_DIR=None):
        if not NCS_RUN_DIR:
            self.NCS_RUN_DIR = "~/ncs-run"
        else:
            self.NCS_RUN_DIR = NCS_RUN_DIR
        self.username = username
        self.password = password
        self.open_session()
        if not log:
            self.log = get_log()
        else:
            self.log = log

    def root(self):
        """
        Get self maapi session root
        :return:
        """
        return ncs.maagic.get_root(self.session)

    def open_session(self):
        """
        Open ans store Maapi session.
        :return: Maapi session
        """
        self.session = ncs.maapi.Maapi()
        ncs.maapi.Session(self.session, self.username, self.password)

    def close_session(self):
        """
        Close session.
        :rtype: object
        """
        self.session.close()

    def open_transaction(self, flag='r'):
        """
        Open a Maapi transaction.
        :return: transaction, nso root
        """
        if flag == 'r':
            t = self.session.start_read_trans()
        elif flag == 'w':
            t = self.session.start_write_trans()
        else:
            raise Exception("Only possible flags are 'r' and 'w', '{}' given")
        root = ncs.maagic.get_root(t)
        return t, root

    def device_platform(self, device_name):
        """
        Get device platform.
        :param device_name: str
        :return: str
        """
        trans, root = self.open_transaction('r')
        device = root.devices.device[device_name]
        return device.platform.name

    def exec_cmd_on_device(self, device_name, command):
        """
        Issue a command on a device using nso live status
        :param device_name: device name
        :param command: command as string
        :return: command output
        """
        device = self.root().devices.device[device_name]
        execute = device.live_status.exec.any
        input = execute.get_input()
        input.args = [command]
        return execute(input).result

    def call_action(self, action_path, **kwargs):
        """
        generic method to call an action under some constraint
        :param action_path:
        :param kwargs:
        :return: action output
        """
        t, root = self.open_transaction()
        action_node = ncs.maagic.get_node(t, action_path)
        act_input = action_node.get_input()
        for k, v in kwargs.items():
            act_input[k] = v
        return action_node(act_input)

    def device_conf(self, device_name):
        """
        Get device conf with live-status.
        :param ned: Device ned
        :param device_name: name of the device
        :return: device conf
        """
        platform = self.device_platform(device_name)
        show_cmd = {'ios': 'show running-conf',
                    'ios-xr': 'show running-conf',
                    'alu-sr': 'admin display-conf',
                    'huawei-vrp': 'display current-conf'}
        config = self.exec_cmd_on_device(device_name, show_cmd[platform])
        return config

    def check_sync(self, device_name):
        """
        Issue a check_sync command for a given device.
        :rtype: String
        :param device_name:
        """
        device = self.root()['devices']['device'][device_name]
        output = device.check_sync()
        return output['result']

    def sync_from(self, device_name):
        """
        Issue a sync-from command throughout NSO for the Device.
    
        :rtype: void
        :param device_name:  Device name
        """
        trans, root = self.open_transaction('w')
        device = root.devices.device[device_name]
        output = device.sync_from()
        if not output.result:
            raise Exception(f"Device sync error for device {device_name}: {output.info}")
        self.log.info(f"synced from {device_name} : {output['result']}")
        trans.finish()

    def packages_reload(self, force=False):
        """
        Issue packages reload command on NSO and raise exception if it fails.
        :param force: force parameter of the command either true of false
        :return: output of the command
        """
        self.log.info('package reload ... ')
        trans, root = self.open_transaction('w')
        input1 = root.packages.reload.get_input()
        if force:
            input1.force.create()
        output = root.packages.reload(input1)
        for r in output.reload_result:
            if not r.result:
                raise Exception(f'Failed to load package {r.package} for reason {r.info}')
        trans.finish()
        self.log.info('Package reload : True')

    def local_conf(self, device, platform):
        """
        NSO get device local conf.
        :param platform:
        :param device: device name
        :param ned: device ned
        :return: nso command output or exception
        """
        output = self.exec_cmd(f"show running-config devices device {device} config {platform}:configuration")
        return output

    def onboard_device(self, device_name, router):
        """
        Onboard a device in NSO.
        :param device_name: device name
        :param router: device data dict
        """
        t, root = self.open_transaction('w')
        self.log.info("Setting device {} configuration ...".format(device_name))
        device_list = root.devices.device
        device = device_list.create(device_name)
        device.address = router['address']
        device.port = router['port']
        device.authgroup = router['auth']
        dev_type = device.device_type[router['type']]
        dev_type.ned_id = router['ned-id']
        device.state.admin_state = 'unlocked'
        self.log.info('Committing the device configuration...')
        t.apply()
        self.log.info("Device {} created".format(device_name))

    def connect_device(self, device_name, session=None):
        """
        NSO Connect to a device.
        :param session: maapi session
        :param device_name: device name
        """
        device = self.root().devices.device[device_name]
        self.log.info("Connecting device {} ...".format(device_name))
        output = device.connect()
        self.log.info("Result: {}".format(output.result))

    def fetch_host_keys(self, device_name, session=None):
        """
        NSO fetch host keys of a device.
        :type session: maapi session
        :param device_name: device name
        """
        device = self.root().devices.device[device_name]
        self.log.info("Fetching SSH keys...")
        output = device.ssh.fetch_host_keys()
        if not output.result:
            raise Exception("Fetching host key for device {} failed!".format(device_name))
        self.log.info("Result: {}".format(output.result))

    def create_auth_group(self, name, username, password):
        """
        NSO create authentication group default map.
        :param name: auth group name
        :param username: username
        :param password: password
        """
        t, root = self.open_transaction('w')
        lab = root['devices'].authgroups.group.create(name)
        map_lab1 = lab.default_map.create()
        map_lab1.remote_name = username
        map_lab1.remote_password = password
        t.apply()

    def apply_template(self, template_path, no_networking=False, encode="xml"):
        """
        apply template
        :param template_path:
        :param no_networking:
        :return:
        """
        no_net = '-n ' if no_networking else ''
        ftype = '-F N' if encode == "json" else '-F x'
        cmd = f"ncs_load -lm {no_net}{ftype} {template_path}"
        self.run_shell_cmd(cmd)

    def exec_cmd(self, cmd):
        """
        Issue an NSO command throughout shell.
        :param command: NSO Command
        :return: NSO output of the command
        """
        std_out, std_err = self.run_shell_cmd(f"""ncs_cli -C -u admin << EOF\n{cmd}\nEOF""")
        return std_out

    def netsim_commit_conf(self, netsim, cmd):
        """
        Issue an NSO command throughout shell.
        :param command: NSO Command
        :return: NSO output of the command
        """
        std_out, std_err = self.run_shell_cmd(
            f"""cd {self.NCS_RUN_DIR}/packages && ncs-netsim cli-c {netsim} <<EOF\nconfig\n{cmd}\ncommit\nEOF""")
        return std_out

    def make_package(self, package):
        """
        compile a package
        :param package:
        :return:
        """
        self.run_shell_cmd(f"cd {self.NCS_RUN_DIR}/packages/{package}/src && make clean && make")

    def delete_device(self, dev_name=None):
        """
        clean nso device tree
        :return:
        """
        t, root = self.open_transaction('w')
        if not dev_name:
            del root.devices.device
        else:
            del root.devices.device[dev_name]
        t.apply()

    def del_node(self, kp):
        trans, root = self.open_transaction('w')
        node = ncs.maagic.cd(root, kp)
        trans.apply()

    def run_shell_cmd(self, cmd):
        """
        run shell command
        :param cmd:
        :return:
        """
        self.log.info(f"Running cmd : {cmd} ...")
        pipes = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        std_out, std_err = pipes.communicate()
        if pipes.returncode != 0:
            err_msg = "{}. Code: {}".format(std_err.decode("utf-8"), pipes.returncode)
            self.log.error(err_msg)
            raise Exception(err_msg)

        elif len(std_err):
            self.log.warning(std_err)

        else:
            self.log.info(std_out.decode("utf-8"))

        return std_out, std_err

    def netsim_list(self):
        """
        Get netsims list
        :return:
        """
        import re
        std_out, std_err = self.run_shell_cmd(f"cd {self.NCS_RUN_DIR}/packages "
                                              "&& ncs-netsim list")
        devices = re.findall(r'name=(\S+)', std_out.decode("utf-8"))
        return devices

    def delete_netsims(self):
        """
        delete all netsim network
        :return:
        """
        try:
            netsim_list = self.netsim_list()
            self.run_shell_cmd(f"cd {self.NCS_RUN_DIR}/packages "
                               "&& ncs-netsim delete-network")
            for dev_name in netsim_list:
                self.delete_device(dev_name)
        except Exception as e:
            pass

    def start_netsim(self, device_name):
        """
        start netsim
        :param device_name:
        :return:
        """
        self.run_shell_cmd(f"cd {self.NCS_RUN_DIR}/packages "
                           f"&& ncs-netsim start {device_name}")

    def onboard_netsim(self, device=''):
        """
        Onboard netsim into nso device tree
        :param device:
        :return:
        """
        self.run_shell_cmd(f"cd {self.NCS_RUN_DIR}/packages "
                           f"&& ncs-netsim ncs-xml-init {device} > device{device}.xml "
                           f"&& ncs_load -l -m device{device}.xml "
                           f"&& rm device{device}.xml")

    def make_netsim(self, device_name, ned_id):
        """
        crate netsim
        :param device_name:
        :param ned_id:
        :return:
        """
        try:
            self.run_shell_cmd(f"cd {self.NCS_RUN_DIR}/packages "
                               f"&& ncs-netsim create-device {ned_id} {device_name}")
        except:
            self.run_shell_cmd(f"cd {self.NCS_RUN_DIR}/packages "
                               f"&& ncs-netsim add-device {ned_id} {device_name}")

    def compare_expect(self, conf1, conf2, expect_added_path, expect_removed=""):
        """
        compare two configs and expect diff
        :param conf2:
        :param expect_added_path:
        :param expect_removed:
        :return:
        """
        same, added, removed = self.compare_configs(conf1, conf2)

        if ''.join(removed.split()) != ''.join(expect_removed.split()):
            _same, _added, _removed = self.compare_configs(removed, expect_removed)
            self.log.error("Difference removed:::removed:::\n{}\nDifference removed:::added:::{}".format(_removed, _added))
            raise Exception("Removed and ExpectRemoved don't match")

        with open(expect_added_path, 'r') as f:
            expect_added = f.read()

        if ''.join(added.split()) != ''.join(expect_added.split()):
            _same, _added, _removed = self.compare_configs(added, expect_added)
            self.log.error(f"Difference removed:::removed:::\n{_removed}\nDifference removed:::added:::{_added}")
            raise Exception("Added and ExpectAdded don't match")

        self.log.ingf('Compare and expect -> success')

    def compare_configs(self, f1, f2):
        """
        Compare two configs and output diffs
        :param f1: file or str of first config
        :param f2: file or str of second config
        :return:
        """
        self.log.info("Comparing configs ...")
        added = ""
        removed = ""
        same = True
        try:
            stream1 = open(f1, "r")
            stream2 = open(f2, "r")
        except:
            from io import StringIO
            stream1 = StringIO(f1)
            stream2 = StringIO(f2)
        stream1 = [line.lstrip() for line in stream1.readlines()[: -1]]
        stream2 = [line.lstrip() for line in stream2.readlines()[: -1]]
        diff = difflib.ndiff(stream1, stream2)
        for line in diff:
            if line.startswith('+') and not line.startswith(('+ # Generated', '+ # Finished', '+ !!')):
                added = added + line[2:]
                same = False
            elif line.startswith('-') and not line.startswith(('- # Generated', '- # Finished', '- !!')):
                removed = removed + line[2:]
                same = False
        if same:
            self.log.info("Pre and Post device configs are identical!")
        return [same, added, removed]
