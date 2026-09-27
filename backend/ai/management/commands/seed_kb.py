"""Seeds a small set of hand-written, genuinely actionable IT helpdesk KB articles into Qdrant.

Why this exists: the indexed Hugging Face dataset (`manage.py index_dataset`) is generic
multi-industry customer support data. Most of its "resolution" text is a first-reply template
("could you share more details?") rather than an actual fix, so the auto-answer path in
ai/pipeline.py almost never fires against it - there's nothing concrete to cite. This command adds
real, step-by-step IT helpdesk articles for the everyday categories, using point ids starting at
KB_ID_OFFSET so they never collide with the dataset's ids (which run 0..~23641).
"""

from django.conf import settings
from django.core.management.base import BaseCommand
from qdrant_client import models

from ai.embeddings import get_dense_model, get_sparse_model
from ai.qdrant_client import ensure_collection, get_client

KB_ID_OFFSET = 900001

ARTICLES = [
    # --- VPN Access (safe_to_auto_solve) ---
    {
        "category": "VPN Access",
        "subject": "VPN client keeps disconnecting every few minutes",
        "body": "My VPN client on my work laptop disconnects every 5-10 minutes and I have to "
        "keep reconnecting manually. It's been happening for a day or two.",
        "resolution": "This is usually caused by the laptop's wifi adapter power-saving mode "
        "interrupting the tunnel. 1. Open Device Manager > Network adapters, right-click your "
        "wifi adapter > Properties > Power Management, and uncheck 'Allow the computer to turn "
        "off this device to save power'. 2. In the VPN client settings, disable 'Reconnect on "
        "network change' if enabled, then reconnect once. 3. If it still drops, switch the VPN "
        "protocol from UDP to TCP in the client's connection settings - this is more stable on "
        "flaky wifi. 4. Restart the laptop after making these changes.",
    },
    {
        "category": "VPN Access",
        "subject": "VPN connection fails with authentication error",
        "body": "When I try to connect to the company VPN I get an 'authentication failed' error "
        "even though I'm sure my password is correct.",
        "resolution": "1. Confirm you're using your network/domain password, not your email "
        "password - they can differ. 2. If your password was recently changed, the VPN client "
        "may have a cached credential: open the VPN client, go to Settings > Forget saved "
        "credentials (or delete the connection profile and re-add it), then reconnect and enter "
        "the new password. 3. Check that your account isn't locked from too many failed attempts "
        "(see the Account Access lockout article) before retrying. 4. If it still fails, confirm "
        "the VPN server address in the client matches the one on the IT intranet page, since it "
        "occasionally changes after infrastructure updates.",
    },
    {
        "category": "VPN Access",
        "subject": "VPN connects but I have no internet access",
        "body": "The VPN shows as connected but I can't reach any websites or internal tools "
        "while it's on.",
        "resolution": "This is almost always a DNS or 'route all traffic' setting issue. 1. Open "
        "the VPN client settings and make sure 'Use default gateway on remote network' (or "
        "equivalent 'route all traffic through VPN') is enabled. 2. Flush the local DNS cache: "
        "open Command Prompt as admin and run `ipconfig /flushdns`, then reconnect the VPN. "
        "3. If you're on wifi, try switching to a wired connection temporarily to rule out a "
        "local network issue. 4. If only internal tools are unreachable (public sites work fine), "
        "the split-tunnel routes may be misconfigured - reinstall the VPN client's default profile.",
    },
    # --- Wifi Connectivity (safe_to_auto_solve) ---
    {
        "category": "Wifi Connectivity",
        "subject": "Laptop won't connect to the office wifi",
        "body": "My laptop can see the office wifi network in the list but won't connect - it "
        "just says 'Can't connect to this network'.",
        "resolution": "1. Click the network, choose 'Forget this network', then reconnect and "
        "re-enter the wifi password from the IT intranet page. 2. Toggle wifi off and on (or "
        "restart the laptop) to reset the adapter. 3. On Windows, run `netsh winsock reset` and "
        "`netsh int ip reset` in an admin Command Prompt, then restart. 4. If other devices "
        "connect fine but only this laptop fails, update the wifi adapter driver from Device "
        "Manager > Network adapters > right-click > Update driver.",
    },
    {
        "category": "Wifi Connectivity",
        "subject": "Wifi keeps dropping intermittently throughout the day",
        "body": "My connection to the office wifi drops every 20-30 minutes and reconnects on "
        "its own after a few seconds. It's disruptive during calls.",
        "resolution": "1. Disable wifi adapter power-saving: Device Manager > Network adapters > "
        "your wifi adapter > Properties > Power Management tab > uncheck 'Allow the computer to "
        "turn off this device to save power'. 2. Move closer to the nearest access point if "
        "possible - dead zones between APs cause repeated roaming drops. 3. Forget and re-add the "
        "network so the laptop picks the strongest available access point fresh. 4. If it "
        "persists for multiple people in the same area, report it as a Network Outage instead so "
        "the access point itself can be checked.",
    },
    {
        "category": "Wifi Connectivity",
        "subject": "Wifi shows connected but no internet access",
        "body": "My laptop says I'm connected to the office wifi with full signal, but no "
        "websites or internal tools load.",
        "resolution": "1. Run `ipconfig /release` then `ipconfig /renew` in an admin Command "
        "Prompt to get a fresh IP address from the router. 2. Run `ipconfig /flushdns` to clear "
        "stale DNS entries. 3. Check the taskbar wifi icon for an exclamation mark, which usually "
        "means limited connectivity - forget the network and reconnect. 4. Try a different device "
        "on the same wifi; if it also fails, the access point/router itself is down and this "
        "should be reported as a Network Outage instead.",
    },
    # --- Password Reset (safe_to_auto_solve) ---
    {
        "category": "Password Reset",
        "subject": "Forgot my account password and I'm locked out",
        "body": "I forgot the password to log into my company account and can't get in. How do I "
        "reset it myself?",
        "resolution": "1. Go to the company self-service password portal (linked from the IT "
        "intranet homepage) and click 'Forgot password'. 2. Enter your work email address and "
        "complete the identity check (usually a code sent to your registered personal email or "
        "phone). 3. Choose a new password meeting the policy (12+ characters, at least one number "
        "and symbol). 4. Wait 1-2 minutes for the change to sync, then log in again - if you use "
        "the same account on your phone or other devices, update the password there too so they "
        "don't keep failing and lock the account again.",
    },
    {
        "category": "Password Reset",
        "subject": "Password reset email never arrives",
        "body": "I requested a password reset link but it never shows up in my inbox, even after "
        "10+ minutes.",
        "resolution": "1. Check your Junk/Spam folder - reset emails are frequently filtered "
        "there. 2. Confirm you entered your correct work email address, not a personal one, when "
        "requesting the reset. 3. Reset links expire after 15 minutes; if it's been longer, "
        "request a new one rather than waiting for the old email. 4. If it still doesn't arrive "
        "after a fresh request and a spam-folder check, your account's registered recovery email "
        "may be outdated - this needs an agent to update it manually.",
    },
    {
        "category": "Password Reset",
        "subject": "Password expired and I need to set a new one",
        "body": "I got a notice that my password expired and I'm being prompted to change it but "
        "not sure how.",
        "resolution": "1. At the login prompt, click 'Change password' rather than trying to log "
        "in with the old one. 2. Enter the old (expired) password once, then set a new password "
        "meeting policy (12+ characters, a number, and a symbol) that you haven't used in the "
        "last 5 changes. 3. If working remotely, connect to VPN first since password changes only "
        "sync while connected to the company network. 4. Update the password in any saved logins "
        "(browser, email client, phone) to avoid repeated failed-login lockouts.",
    },
    # --- Software Installation (safe_to_auto_solve) ---
    {
        "category": "Software Installation",
        "subject": "Software install is blocked - administrator permission required",
        "body": "I'm trying to install an approved application from the software catalog but I "
        "get an 'administrator permission required' popup and can't proceed.",
        "resolution": "1. Open the Company Software Portal (not the installer file directly) and "
        "search for the application there - approved software installs through it without "
        "needing admin rights. 2. If it's not listed in the portal, it may not yet be approved "
        "for self-install; this needs to be requested through IT rather than installed directly. "
        "3. If the portal itself won't open, restart the laptop first, since it sometimes needs a "
        "pending policy update to apply.",
    },
    {
        "category": "Software Installation",
        "subject": "Application installation fails with an error code",
        "body": "Trying to install a piece of software and the installer fails partway through "
        "with an error code, then rolls back.",
        "resolution": "1. Free up disk space - installers often fail silently or with a generic "
        "error when the drive is nearly full; aim for at least 5GB free. 2. Temporarily disable "
        "antivirus real-time scanning during the install, as it sometimes blocks installer "
        "components, then re-enable it afterward. 3. Download the installer again in case the "
        "original file was corrupted. 4. Run the installer as Administrator (right-click > Run "
        "as administrator) rather than double-clicking it.",
    },
    {
        "category": "Software Installation",
        "subject": "Need to reinstall a printer or scanner driver",
        "body": "My printer stopped working after a Windows update and I think the driver needs "
        "to be reinstalled.",
        "resolution": "1. Go to Settings > Bluetooth & devices > Printers & scanners, select the "
        "printer, and click Remove device. 2. Restart the laptop. 3. Reinstall it via the "
        "Company Software Portal's printer setup tool, which pulls the correct driver for your "
        "model automatically, or use Settings > Add device if it's a network printer. 4. Print a "
        "test page from the printer's properties to confirm it's working again.",
    },
    # --- Peripheral Request (safe_to_auto_solve) ---
    {
        "category": "Peripheral Request",
        "subject": "My mouse or keyboard stopped working and I need a replacement",
        "body": "My wireless mouse has stopped responding even with a fresh battery - I think it "
        "needs to be replaced.",
        "resolution": "1. First confirm it's the device and not the receiver: try the mouse on "
        "another laptop, or try a different mouse with the same USB receiver, to isolate the "
        "fault. 2. If it's the receiver, re-pair it by holding the mouse's connect button for 5 "
        "seconds while the receiver is plugged in. 3. If the mouse itself is faulty, submit a "
        "peripheral request through the IT portal with your asset tag, and a replacement will be "
        "issued from the hardware store on your next visit or shipped to you.",
    },
    {
        "category": "Peripheral Request",
        "subject": "Requesting a docking station for my laptop",
        "body": "I'd like to request a docking station so I can connect multiple monitors and "
        "peripherals to my laptop at my desk.",
        "resolution": "1. Submit a peripheral request through the IT portal specifying 'docking "
        "station' and your laptop model (docks are model-specific for USB-C vs Thunderbolt). "
        "2. Standard docking stations are pre-approved for all full-time staff and typically ship "
        "or are available for pickup within 2-3 business days. 3. Once received, connect it via "
        "the single USB-C/Thunderbolt cable to your laptop, then plug monitors, keyboard, and "
        "mouse into the dock rather than the laptop directly.",
    },
    {
        "category": "Peripheral Request",
        "subject": "Headset not working, need a replacement for calls",
        "body": "My headset has no sound and the microphone isn't picked up in calls anymore.",
        "resolution": "1. Test the headset on another device to confirm the fault is in the "
        "headset itself and not a software/driver setting. 2. If using USB, try a different USB "
        "port; if using a 3.5mm jack, check it's fully inserted (a partial insert mutes the mic). "
        "3. In Sound settings, confirm the headset is selected as both default input and output "
        "device, not the laptop's built-in mic/speakers. 4. If the hardware itself is faulty, "
        "submit a peripheral request through the IT portal for a replacement headset.",
    },
    # --- Monitor Issue (safe_to_auto_solve) ---
    {
        "category": "Monitor Issue",
        "subject": "External monitor not detected when connected to laptop",
        "body": "I connected my external monitor via HDMI but my laptop doesn't detect it at "
        "all.",
        "resolution": "1. Check the cable is fully seated at both ends, and try a different "
        "cable/port if available to rule out a faulty cable. 2. Press Windows key + P and select "
        "'Extend' or 'Duplicate' to force Windows to re-scan for displays. 3. If using a "
        "docking station, make sure the dock's own drivers are up to date via the Company "
        "Software Portal. 4. Restart the laptop with the monitor already connected and powered "
        "on, since some laptops only detect displays during boot.",
    },
    {
        "category": "Monitor Issue",
        "subject": "Monitor screen flickers or randomly loses signal",
        "body": "My external monitor flickers on and off throughout the day and sometimes shows "
        "'No signal' for a few seconds before coming back.",
        "resolution": "1. Reseat the video cable at both the monitor and laptop/dock ends - "
        "loose connections are the most common cause. 2. Try a different cable and a different "
        "port on the laptop or dock to isolate whether it's the cable, port, or monitor. 3. Lower "
        "the refresh rate in Settings > Display > Advanced display if it's set above the "
        "monitor's rated maximum. 4. If the flickering continues with a known-good cable and "
        "port, the monitor itself likely needs to be swapped - request a replacement through the "
        "IT portal.",
    },
    {
        "category": "Monitor Issue",
        "subject": "Monitor resolution is stuck at the wrong setting",
        "body": "My monitor looks blurry or the icons are too big - the resolution seems wrong "
        "and I can't fix it.",
        "resolution": "1. Right-click the desktop > Display settings, select the monitor, and "
        "set Resolution to the one marked '(Recommended)' for that display. 2. If no recommended "
        "resolution is listed or it looks wrong, the monitor driver may need updating - go to "
        "Display settings > Advanced display > Display adapter properties > List All Modes to "
        "pick the native resolution manually. 3. Make sure you're using a cable that supports the "
        "monitor's native resolution (older VGA/basic HDMI cables can cap it lower than DisplayPort).",
    },
    # --- Network Outage (not safe_to_auto_solve - for agent context only) ---
    {
        "category": "Network Outage",
        "subject": "Entire floor has no network or wifi access",
        "body": "Nobody on my floor can connect to wifi or wired network - it's affecting the "
        "whole team, not just me.",
        "resolution": "This indicates a switch or access point outage affecting multiple users "
        "rather than a single-device issue. An on-site technician needs to check the floor's "
        "network switch and access points directly; this cannot be resolved remotely by the "
        "affected employees. Escalate immediately as it blocks multiple people's work.",
    },
    # --- Laptop Issue (not safe_to_auto_solve - for agent context only) ---
    {
        "category": "Laptop Issue",
        "subject": "Laptop won't turn on or charge",
        "body": "My laptop won't power on at all, and the charging light doesn't come on when I "
        "plug it in either.",
        "resolution": "Try a different charging cable/adapter and a different power outlet first "
        "to rule out a faulty charger. If the laptop still shows no sign of power (no lights, no "
        "fan, nothing) with a known-good charger, this is a hardware fault requiring a technician "
        "to inspect the device in person or issue a loaner while it's repaired.",
    },
    # --- Account Access (not safe_to_auto_solve - for agent context only) ---
    {
        "category": "Account Access",
        "subject": "Account locked after too many failed login attempts",
        "body": "I tried logging in a few times with what I thought was the right password and "
        "now it says my account is locked.",
        "resolution": "Account lockouts after repeated failed attempts require an agent to verify "
        "identity and manually unlock the account before a password reset can proceed - this "
        "cannot be self-served for security reasons. The employee should be directed to contact "
        "IT directly rather than continuing to retry, as further attempts extend the lockout.",
    },
]


class Command(BaseCommand):
    help = "Seed hand-written, actionable IT helpdesk KB articles into Qdrant (see module docstring)."

    def handle(self, *args, **options):
        client = get_client()
        ensure_collection(client, settings.QDRANT_COLLECTION)

        dense_model = get_dense_model()
        sparse_model = get_sparse_model()

        texts = [f"{a['subject']}\n{a['body']}" for a in ARTICLES]
        dense_vecs = list(dense_model.embed(texts))
        sparse_vecs = list(sparse_model.embed(texts))

        points = [
            models.PointStruct(
                id=KB_ID_OFFSET + i,
                vector={
                    "dense": dense.tolist(),
                    "sparse": models.SparseVector(indices=sparse.indices.tolist(), values=sparse.values.tolist()),
                },
                payload={
                    "subject": article["subject"],
                    "body": article["body"],
                    "resolution": article["resolution"],
                    "category": article["category"],
                    "queue": "IT Support",
                    "priority": "medium",
                    "language": "en",
                    "resolved": True,
                    "restricted": False,
                    "source": "manual_kb",
                },
            )
            for i, (article, dense, sparse) in enumerate(zip(ARTICLES, dense_vecs, sparse_vecs))
        ]
        client.upsert(collection_name=settings.QDRANT_COLLECTION, points=points)
        self.stdout.write(self.style.SUCCESS(f"Seeded {len(points)} manual KB articles."))
