import argparse
import paramiko
import socket
import sys


def ssh_connect(hostname):
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        private_key = paramiko.RSAKey.from_private_key_file('/root/.ssh/id_rsa')
        ssh.connect(hostname, username='root', pkey=private_key, timeout=10)
        return ssh
    except Exception as e:
        raise Exception(f"SSH connection failed")


def get_os_type(ssh_client):
    stdin, stdout, stderr = ssh_client.exec_command("cat /etc/os-release")
    output = stdout.read().decode().lower()
    if 'debian' in output:
        return 'debian'
    elif 'centos' in output or 'almalinux' in output:
        return 'centos'
    else:
        raise Exception("Unsupported OS")


def get_load_average(ssh_client):
    stdin, stdout, stderr = ssh_client.exec_command("uptime")
    output = stdout.read().decode()
    load_part = output.split('load average:')[1].strip().split(',')[0]
    return float(load_part)


def install_postgresql(ssh_client, os_type):
    if os_type == 'debian':
        commands = [
            'apt-get update -qq',
            'apt-get install -y postgresql postgresql-contrib'
        ]
    elif os_type == 'centos':
        commands = [
            'yum install -y postgresql-server postgresql-contrib',
            'postgresql-setup initdb',
            'systemctl enable postgresql',
            'systemctl start postgresql'
        ]
    else:
        raise Exception("Unsupported OS")

    for cmd in commands:
        stdin, stdout, stderr = ssh_client.exec_command(cmd)
        exit_status = stdout.channel.recv_exit_status()
        if exit_status != 0:
            error = stderr.read().decode()
            raise Exception(f"Command '{cmd}' failed: {error}")


def get_postgresql_conf_path(ssh_client):
    stdin, stdout, stderr = ssh_client.exec_command(
        'sudo -u postgres psql -t -c "SHOW config_file;"'
    )
    path = stdout.read().decode().strip()
    if not path:
        raise Exception("Cannot find PostgreSQL config file")
    return path


def get_pg_hba_path(ssh_client):
    stdin, stdout, stderr = ssh_client.exec_command(
        'sudo -u postgres psql -t -c "SHOW hba_file;"'
    )
    path = stdout.read().decode().strip()
    if not path:
        raise Exception("Could not find pg_hba.conf")
    return path


def configure_postgresql(ssh_client, os_type, other_server_ip):
    postgresql_conf = get_postgresql_conf_path(ssh_client)
    sftp = ssh_client.open_sftp()
    try:
        with sftp.file(postgresql_conf, 'r') as f:
            content = f.read().decode()
        new_content = []
        for line in content.split('\n'):
            if line.strip().startswith('listen_addresses'):
                new_content.append("listen_addresses = '*'")
            else:
                new_content.append(line)
        with sftp.file(postgresql_conf, 'w') as f:
            f.write('\n'.join(new_content))
    finally:
        sftp.close()

    pg_hba_conf = get_pg_hba_path(ssh_client)
    sftp = ssh_client.open_sftp()
    try:
        with sftp.file(pg_hba_conf, 'r') as f:
            content = f.read().decode()
        new_line = f"host all student {other_server_ip}/32 md5\n"
        content += new_line
        with sftp.file(pg_hba_conf, 'w') as f:
            f.write(content)
    finally:
        sftp.close()

    cmd = 'systemctl restart postgresql' if os_type == 'debian' else 'systemctl restart postgresql'
    stdin, stdout, stderr = ssh_client.exec_command(cmd)
    exit_status = stdout.channel.recv_exit_status()
    if exit_status != 0:
        error = stderr.read().decode()
        raise Exception(f"Failed to restart PostgreSQL: {error}")


def create_user(ssh_client):
    cmd = """sudo -u postgres psql -c "CREATE USER student WITH PASSWORD 'student';" """
    stdin, stdout, stderr = ssh_client.exec_command(cmd)
    exit_status = stdout.channel.recv_exit_status()
    if exit_status != 0:
        error = stderr.read().decode()
        if 'already exists' not in error:
            raise Exception(f"Failed to create user: {error}")


def test_db(ssh_client):
    cmd = """sudo -u postgres psql -c "SELECT 1;" """
    stdin, stdout, stderr = ssh_client.exec_command(cmd)
    exit_status = stdout.channel.recv_exit_status()
    if exit_status != 0:
        error = stderr.read().decode()
        raise Exception(f"Database test failed: {error}")
    print("Database test successful.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('servers', help='Comma-separated list of servers IPs')
    args = parser.parse_args()

    servers = args.servers.split(',')
    if len(servers) != 2:
        print("Error! Provide only two server addresses.")
        sys.exit(1)

    server_info = []
    for server in servers:
        try:
            ssh = ssh_connect(server)
            os_type = get_os_type(ssh)
            load = get_load_average(ssh)
            server_info.append((server, load, os_type, ssh))
            print(f"Connected to {server}: OS={os_type}, Load={load}")
        except Exception as e:
            print(f"Error processing {server}: {e}")
            sys.exit(1)

    target = min(server_info, key=lambda x: x[1])
    print(f"Selected target server: {target[0]} (load: {target[1]})")
    other_server = [s[0] for s in server_info if s[0] != target[0]][0]
    try:
        other_ip = socket.gethostbyname(other_server)
    except socket.error as e:
        print(f"Failed to resolve {other_server}: {e}")
        sys.exit(1)

    try:
        print("Installing PostgreSQL...")
        install_postgresql(target[3], target[2])
        print("Configuring PostgreSQL...")
        configure_postgresql(target[3], target[2], other_ip)
        print("Creating user 'student'...")
        create_user(target[3])
        print("Testing database...")
        test_db(target[3])
        print("Success!")
    except Exception as e:
        print(f"Setup failed: {e}")
        sys.exit(1)
    finally:
        for info in server_info:
            info[3].close()


if __name__ == '__main__':
    main()