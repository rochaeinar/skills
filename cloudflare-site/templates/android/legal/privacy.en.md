<!--
TEMPLATE · Privacy Policy (English). Read references/app-integration.md first.
Write the final file at <app>/app/src/main/assets/legal/privacy_en.md.
- Every sentence must be TRUE for this app, verified in its code (manifest, Gradle dependencies,
  network calls, storage, backup rules, SDK initialisation). Keep a section only if it applies;
  rewrite it with the app's real features, never copy the example wording blindly.
- Replace every {{PLACEHOLDER}} and delete every comment like this one.
  `web.py legal <slug>` refuses a document that still has "{{" or "<!--".
- Same structure and numbering in every language; natural translations, not literal.
- Not legal advice: the user reviews the final text.
-->
**{{APP}}** · {{DEVELOPER}}  
*Last updated: {{UPDATED_EN}}*

<!-- One or two sentences: who made the app, what it is for, free or paid, "provided as is". -->
{{DEVELOPER}} built **{{APP}}** as {{ONE_LINE_PURPOSE_EN}}. The service is provided as is.

This policy explains what information the app uses, what for and how it is protected.

---

## 1. Information we collect

<!-- Pick ONE opening that is true:
  A) No personal data and no internet (no INTERNET permission in the merged manifest):
     "The app **does not collect personal data** and has no internet connection: nothing you do in
     the app is sent to us or to anyone else."
  B) Only technical, non-identifying data (crash reports, basic usage, approximate country…):
     list each item in bold with what it is and why.
  C) An account, sign-in or user content on a server: list exactly which fields, where they are
     stored and for how long.
  Then: what is stored ON the device (be specific: "computers you paired, your macros and settings").
  Mention sensitive content explicitly when relevant (e.g. "what you type is never stored or logged").
  Local diagnostic logs: say whether they exist and what they never contain. -->

## 2. Permissions

<!-- One bullet per runtime or sensitive permission in the MERGED manifest
  (app/build/intermediates/merged_manifests/release/AndroidManifest.xml, or `aapt2 dump permissions`
  on the release APK): its name as the user sees it in Android ("Nearby devices", "Notifications"…)
  and the concrete reason in this app. Say what each one is NOT used for when users might worry
  (e.g. Bluetooth scanning never used for location). Mention permissions removed from libraries
  (tools:node="remove") only if it helps trust ("the app does not request internet access"). -->

| Permission | What the app uses it for |
| --- | --- |
| {{PERMISSION}} | {{REASON}} |

## 3. Third-party services

<!-- Every SDK that talks to a server or receives data: Firebase (Crashlytics, Analytics),
  Google Play services, AdMob, billing, maps, CDNs, sync APIs, IP geolocation… Find them in the
  Gradle dependencies (`web.py licenses <slug>` lists them), in the code (URLs, API clients) and in
  google-services.json. For each: what it is used for and what it receives.
  If there are none, replace the table with: "The app uses **no third-party services**: no
  analytics, no advertising and no crash reporting." State clearly whether ads are shown and
  whether any service profiles the user for advertising. -->

| Service | What it is used for |
| --- | --- |
| **{{SERVICE}}** | {{USE}} |

## 4. How we use the information

<!-- Only the real purposes, as a short list (make the app work, fix problems, choose language
  content…). Then the negative: "We don't use it to identify you, to track you across other
  services or to show you ads." -->

## 5. Storage and security

<!-- Where data lives: app-private storage on the device, the user's own cloud account, our server.
  Android backup: read android:allowBackup, fullBackupContent and dataExtractionRules — say what is
  included in the user's Google backup and what is excluded (e.g. logs).
  Network: "Connections are encrypted (HTTPS)" only if every endpoint is HTTPS; with no network,
  say that nothing leaves the phone except <the app's real channel, e.g. keystrokes over Bluetooth
  to the computer you connected>. -->

## 6. Sharing

<!-- "We don't sell or share your information." plus any real exception (the third parties above,
  legal obligations). For apps without a server: "We never receive your information, so we cannot
  share it." -->

## 7. Your control and deletion

<!-- How the user deletes each kind of data: in-app actions (delete a macro, forget a device,
  sign out), clearing the app's storage, uninstalling, deleting files in their own cloud account,
  and how to ask us to delete server data if any exists. -->

## 8. Children

<!-- Target audience from the Play Console declaration (ask the user if unknown). Typical:
  "{{APP}} is not directed to children under 13 and does not knowingly collect information from
  them." Must match the age stated in the Terms. -->

## 9. Changes to this policy

We may update this policy. Every change is published here with its new update date; we recommend reviewing it from time to time.

## 10. Contact

If you have questions about this policy, write to us through our website:

**[{{WEB}}]({{WEB_URL}})**
