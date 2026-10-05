import subprocess
import os
import sys

def get_ips():
    try:
        # Get WSL2 IP
        wsl_ip_proc = subprocess.run(["wsl", "hostname", "-I"], capture_output=True, text=True, check=True)
        wsl_ip = wsl_ip_proc.stdout.strip().split()[0]
        
        # Get Windows Gateway IP
        ip_route_proc = subprocess.run(["wsl", "ip", "route"], capture_output=True, text=True, check=True)
        windows_ip = None
        for line in ip_route_proc.stdout.splitlines():
            if "default via" in line:
                windows_ip = line.split()[2]
                break
        
        if not windows_ip:
            print("Error: Could not determine Windows WSL Gateway IP from ip route.")
            return None, None
            
        return wsl_ip, windows_ip
    except Exception as e:
        print(f"Error executing WSL commands: {e}")
        print("Make sure WSL2 is running and Ubuntu is your default distribution.")
        return None, None

def main():
    print("====================================================================")
    print("       FastDDS WSL2 to Windows Unicast Config Generator            ")
    print("====================================================================")
    
    wsl_ip, windows_ip = get_ips()
    if not wsl_ip or not windows_ip:
        sys.exit(1)
        
    print(f"Detected WSL2 Ubuntu IP: {wsl_ip}")
    print(f"Detected Windows Host IP: {windows_ip}")
    
    xml_content = f"""<?xml version="1.0" encoding="UTF-8" ?>
<dds xmlns="http://www.eprosima.com/XMLSchemas/fastrtps_profiles">
    <profiles>
        <participant profile_name="unicast_connection" is_default_profile="true">
            <rtps>
                <builtin>
                    <avoid_builtin_multicast>true</avoid_builtin_multicast>
                    <metatrafficUnicastLocatorList>
                        <locator/>
                    </metatrafficUnicastLocatorList>
                    <initialPeersList>
                        <locator>
                            <udpv4>
                                <address>{windows_ip}</address>
                            </udpv4>
                        </locator>
                        <locator>
                            <udpv4>
                                <address>{wsl_ip}</address>
                            </udpv4>
                        </locator>
                    </initialPeersList>
                </builtin>
            </rtps>
        </participant>
    </profiles>
</dds>
"""
    
    # Write to Windows profile (native \n is fine for FastDDS on Windows)
    user_profile = os.environ.get("USERPROFILE", "C:\\")
    windows_xml_path = os.path.join(user_profile, "fastdds_profile.xml")
    try:
        with open(windows_xml_path, "w", newline='\n') as f:
            f.write(xml_content)
        print(f"\n[Success] Created Windows FastDDS config at: {windows_xml_path}")
    except Exception as e:
        print(f"\n[Error] Failed to write Windows config: {e}")
        
    # Write locally in workspace for easy sharing (Unix line endings)
    local_xml_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fastdds_profile.xml")
    try:
        with open(local_xml_path, "w", newline='\n') as f:
            f.write(xml_content)
        print(f"[Success] Created workspace copy at: {local_xml_path}")
    except Exception as e:
        pass

    # Write directly into WSL2 home directory
    try:
        wsl_write = subprocess.run(
            ["wsl", "bash", "-c", f"cat > ~/fastdds_profile.xml << 'XMLEOF'\n{xml_content}XMLEOF"],
            capture_output=True, text=True, timeout=10
        )
        if wsl_write.returncode == 0:
            print(f"[Success] Wrote FastDDS config directly to WSL2 ~/fastdds_profile.xml")
        else:
            print(f"[Warning] Could not write directly to WSL2: {wsl_write.stderr.strip()}")
    except Exception as e:
        print(f"[Warning] Could not write directly to WSL2: {e}")

    print("\n====================================================================")
    print("FastDDS profiles updated on both Windows and WSL2.")
    print("====================================================================")

if __name__ == "__main__":
    main()
