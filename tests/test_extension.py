import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import app as appmod
import connection_test as ct
from ssh_keys import check_key_file

SECRET = "SUPERSECRETKEYBODY"
KEY = f"-----BEGIN OPENSSH PRIVATE KEY-----\n{SECRET}\n-----END OPENSSH PRIVATE KEY-----\n"


def hostvars(**hosts):
    return json.dumps({"_meta": {"hostvars": hosts}})


def fake_run(inv_json, ping_rc=0, ping_out="server1 | SUCCESS => pong", ping_err=""):
    calls = []

    def run(cmd, **kw):
        calls.append(cmd)
        assert isinstance(cmd, list) and "shell" not in kw
        if cmd[0] == "ansible-inventory":
            return SimpleNamespace(returncode=0, stdout=inv_json, stderr="")
        return SimpleNamespace(returncode=ping_rc, stdout=ping_out, stderr=ping_err)

    run.calls = calls
    return run


def keyfile(tmp_path, content=KEY):
    p = tmp_path / "key"
    p.write_text(content)
    return p


def test_single_server(tmp_path):
    k = keyfile(tmp_path)
    run = fake_run(hostvars(server1={"ansible_private_key_file": None, "ansible_ssh_private_key_file": str(k)}))
    assert ct.load_hosts("x", run) == {"server1": str(k)}
    status, cmd, out = ct.run_ping("x", None, run)
    assert status == "success" and "pong" in out


def test_multiple_servers_shared_and_individual_key(tmp_path):
    k = keyfile(tmp_path)
    run = fake_run(hostvars(
        a={"ansible_ssh_private_key_file": str(k)},
        b={"ansible_ssh_private_key_file": str(k)},
        c={"ansible_ssh_private_key_file": "/other/key"},
    ))
    hosts = ct.load_hosts("x", run)
    assert len(hosts) == 3 and hosts["a"] == hosts["b"] != hosts["c"]
    status, _, out = ct.run_ping("x", "a", run)
    assert status == "success"
    assert run.calls[-1][:2] == ["ansible", "a"]
    status, _, out = ct.run_ping("x", "c", run)
    assert status == "error" and "nicht gefunden" in out


def test_key_checks(tmp_path):
    assert not check_key_file(tmp_path / "missing")[0]
    assert "nicht gefunden" in check_key_file(tmp_path / "missing")[1]
    assert not check_key_file("relative/key")[0]
    assert not check_key_file("")[0]
    bad = keyfile(tmp_path, "not a key")
    assert "kein gültiger" in check_key_file(bad)[1]
    assert check_key_file(keyfile(tmp_path))[0]
    unreadable = tmp_path / "u"
    unreadable.write_text(KEY)
    unreadable.chmod(0)
    import os
    if os.geteuid() != 0:
        ok, msg = check_key_file(unreadable)
        assert not ok and "nicht lesbar" in msg and SECRET not in msg


def test_failed_ping_and_unknown_host():
    run = fake_run(hostvars(s={}), ping_rc=4, ping_out="s | UNREACHABLE! Permission denied (publickey)")
    status, _, out = ct.run_ping("x", None, run)
    assert status == "error" and "Anmeldung verweigert" in out
    assert ct.run_ping("x", "evil; rm -rf /", run)[0] == "error"


def test_sanitize_hides_key():
    assert SECRET not in ct.sanitize(KEY)


def client(tmp_path, monkeypatch):
    inv = tmp_path / "inventory"
    jobs = tmp_path / "jobs"
    inv.mkdir(); jobs.mkdir()
    (inv / "ZAP_Hosting.ini").write_text("[g]\ns1 ansible_host=1.2.3.4\n")
    (jobs / "p.yml").write_text("- hosts: all\n")
    monkeypatch.setattr(appmod, "INVENTORY_DIR", inv)
    monkeypatch.setattr(appmod, "JOB_DIR", jobs)
    return appmod.app.test_client()


def test_web_invalid_inventory_name(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    r = c.post("/connection-test", data={"inventory": "../../etc/passwd"})
    assert "Ungültiges Inventory" in r.get_data(as_text=True)


def test_web_connection_test_no_key_leak(tmp_path, monkeypatch, capsys):
    c = client(tmp_path, monkeypatch)
    k = keyfile(tmp_path)
    run = fake_run(hostvars(s1={"ansible_ssh_private_key_file": str(k)}), ping_rc=4, ping_err=KEY)
    monkeypatch.setattr(ct.subprocess, "run", run)
    monkeypatch.setattr(ct, "run_ping", ct.run_ping)
    r = c.post("/connection-test", data={"inventory": "ZAP_Hosting.ini", "host": "s1"})
    body = r.get_data(as_text=True)
    assert r.status_code == 200 and SECRET not in body
    captured = capsys.readouterr()
    assert SECRET not in captured.out + captured.err


def test_playbook_run_still_works(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    seen = {}

    def run(cmd, **kw):
        seen["cmd"] = cmd
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(appmod.subprocess, "run", run)
    assert c.get("/").status_code == 200
    r = c.post("/", data={"inventory": "0", "playbook": "0"})
    assert seen["cmd"][0] == "ansible-playbook" and "ok" in r.get_data(as_text=True)
    assert c.post("/", data={"inventory": "9", "playbook": "0"}).status_code == 200
