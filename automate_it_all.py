import os
from pynso import PyNSO

__base_dir__ = os.path.dirname(os.path.realpath(__file__))
__testbed_dir__ = os.path.join(__base_dir__, 'testbed')
__ncs_run_dir__ = "~/ncs-run"
nso = PyNSO(NCS_RUN_DIR=__ncs_run_dir__)
DEVICE_TEST = 'some_device'


def generic_test(device_name, payload_path, expected_path):
    os_mkdir('../tmp')
    save_to_file('../tmp/pre', nso.device_conf(device_name))
    nso.apply_template(payload_path)
    save_to_file('../tmp/post', nso.device_conf(device_name))
    nso.compare_expect('tmp/pre', 'tmp/post', expected_path)


def get_service_output_config(device_name, payload_path):
    os_mkdir('../tmp')
    save_to_file('../tmp/pre', nso.device_conf(device_name))
    nso.apply_template(payload_path)
    save_to_file('../tmp/post', nso.device_conf(device_name))
    same, added, removed = nso.compare_configs("tmp/pre", "tmp/post")
    return added


def create_test_netsims():
    test_devices = ['another_device', 'some_device']
    nso.delete_netsims()
    for device in test_devices:
        nso.make_netsim(device, 'cisco-iosxr-cli-7.21')
        nso.start_netsim(device)
        nso.netsim_commit_conf(device, "tailfned api service-policy-list")
        nso.onboard_netsim(device)
        nso.exec_cmd(f"devices device {device} sync-from")


def prepare_nso_for_service():
    nso.make_package('service-package-name')
    nso.exec_cmd("packages reload force")
    nso.apply_template("a_payload_path", no_networking=True)
    nso.apply_template("another_payload_path"), no_networking=True)
    nso.apply_template("another_payload...")


if __name__ == "__main__":
    # This code right here will load payloads from a testbed folder 
    # Apply them and get the output result in Netsims
    # Then you can use the function generic test to do non regression tests with those 
    # generated payloads
    # isn't this awsome !!
    clean_nso()
    create_test_netsims()
    prepare_nso_for_service()
    for file_name in iter(os.listdir(__testbed_dir__)):
        if file_name.endswith('payload.xml'):
            service_type = file_name.split('-payload.xml')[0]
            save_to = os.path.join(__testbed_dir__, f"{service_type}-expect.cfg")
            output = get_service_output_config(DEVICE_TEST, file_name)
            save_to_file(save_to, output)
