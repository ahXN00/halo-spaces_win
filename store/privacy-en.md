halo.spaces privacy policy

halo.spaces runs entirely inside Thunderbird. It has no server, no account, no analytics and no telemetry, and it never sends your messages, contacts or events anywhere.

Network requests it makes:

1. Sender logos (can be turned off: Preferences → "Logos from sender websites"). For messages from organisations (not from common free-mail providers such as Gmail or Outlook.com), halo.spaces looks up the sender domain's BIMI record via DNS and asks that domain's own website for its logo or icon (for example https://example.com/favicon.ico). Only the domain name is used – never the full address, the subject or the content. The request goes directly to the sender's website, which can see your IP address, just like when you open that website. Logos are cached locally in your Thunderbird profile for 30 days.

2. Contact photos that you have stored as a web link in your own address book are loaded from that link.

3. Update checks: Thunderbird itself checks addons.thunderbird.net for new versions, as with every add-on.

Data stored locally (only in your Thunderbird profile): the logo cache, your halo.spaces settings, and – only if you turn on "Detailed log" – a debug log file that may contain sender addresses.

Optional, macOS only and off by default: "Photos from the Contacts app" reads pictures from your local macOS Contacts database; macOS asks for permission once. Nothing leaves your computer.

Feedback: the "Send Feedback" button only opens a new message window in Thunderbird, addressed to the developer; nothing is sent unless you send it yourself.

Contact: https://github.com/sruf79/halo-spaces/issues
