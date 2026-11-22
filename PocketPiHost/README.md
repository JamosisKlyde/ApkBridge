# Pocket Pi-hole Host — prototype v0.1

Experimental GrapheneOS Android controller for a Pi-hole Docker container running inside Podroid's Alpine Linux virtual machine. This is **not** Docker embedded into the APK: install Podroid separately and start its VM. Android root is not required.

## Build

Open [the Pocket Pi-hole APK build workflow](../../actions/workflows/pocket-pihole-apk.yml). Select the `pocket-pihole-v0.1-prototype` branch and run the workflow if needed. Download the debug APK from the run's Artifacts section. Debug APKs are for testing.

## Connect

The app uses these local phone port forwards:
- Android host TCP 9090 -> Linux guest TCP 9090: token-protected Pi-hole control service.
- Android host TCP 8081 -> Linux guest TCP 8080: Pi-hole web dashboard.

The VM requires the companion installer and Python agent, included in the complete `PocketPiHost_v0.1_source.zip` package supplied in the chat. Run `pihole-host-setup.sh` inside Podroid's Alpine Linux VM as root. The setup script supplies the 64-character access token for the APK. Never publish the token.

**Security:** Podroid's port forwarding may bind to the phone's Wi-Fi interface rather than loopback. Do not add WAN port forwarding, and only use the controller on a trusted network. The API restricts commands to container start/stop/restart/status and blocklist updates. Do not expose Docker's daemon port.

## Important limitations

- The Podroid VM must be started manually before the controller can operate.
- The APK cannot guarantee 24/7 Android background execution, or keep Pi-hole working when the phone is powered off.
- Standard home-network DNS on port 53 isn't solved by the Android controller.
- Tailscale in the VM is an experiment and must be verified before changing any device's DNS.
- Keep the Fedora Pi-hole at 192.168.0.83 as your primary until the phone-hosted container is verified.
