---
title: Administration
summary: Manage users, make roles and choose their permissions, sign people out, read the audit log, and check the system. For administrators.
order: 50
keywords: admin administration users roles permissions grant revoke deactivate reset password sessions audit log system ui kit
permission: lattice.users.manage
---

**Administration** (the shield icon in the rail) shows the parts you have
permission for. Administrators see all of it; someone allowed only to read the
audit log sees just **Audit log**.

## Users

**Users** lists everyone who can sign in. Views show **All**, **Active** and
**Inactive** users.

| To | Do |
|---|---|
| Add a user | **New user**: enter their email, name and roles. Leave the password empty for someone who signs in with single sign-on; otherwise they must change the password you set at first sign-in |
| Give or take away a role | Select users, then **Grant role** or **Remove role**, and choose the role |
| Stop someone signing in | Select them and choose **Deactivate**. They are signed out at once. **Activate** lets them back in |
| Reset a password | Select one user and choose **Reset password**. A temporary password is shown once; give it to the user privately. They must change it at next sign-in |
| Sign someone out | Select them and choose **Sign out everywhere** |
| Change a name, roles or status | Open the user. Their page also shows their sessions and activity |

To protect against lock-out, you cannot remove your own admin role or
deactivate yourself.

People who sign in with single sign-on for the first time get an account
automatically. Depending on how your site is set up, they either get a default
role or wait on **Access pending** until you grant one.

## Roles

A **role** is a named set of **permissions**: the things its members may do,
such as "Edit work items" or "Read the audit log". Each app adds its own
permissions. A user can have several roles; they get every permission of every
one.

**Roles** lists every role with its number of permissions and members.

| Role | Has |
|---|---|
| Administrator | Every permission, always. It cannot be edited |
| Editor | What the apps give it, such as editing work items. You can change it |
| Viewer | Reading, with no extra permissions. You can change it |

| To | Do |
|---|---|
| Make a role | **New role**: a code such as `auditor`, a name and a description, then tick its permissions |
| Change what a role allows | Open the role, tick or untick permissions, and choose **Save role** |
| See who has a role | Open the role: its members are listed at the bottom |
| Give a role to people | In **Users**, select them and choose **Grant role** |
| Delete a role | Select it and choose **Delete**. Built-in roles, and roles that people still have, are kept |

Changes to roles take effect at each person's next page load, and are recorded
in the audit log.

For example, to let someone read the audit log without managing users: make an
**Auditor** role with only **Read the audit log** ticked, and grant it to them.

## Sessions

**Sessions** lists every active sign-in, for all users: who, how they signed
in, from where, and when it was last used. Select sessions and choose
**Revoke** to end them. Your own current session is kept.

## Audit log

**Audit log** records every change made by anyone, in every app: who did it,
what they did, to which record, and when. Filter it by event or by target to
answer "who changed this?".

Each record's own page also shows its history, under **Activity**.

## Email

**Email** lists every email the site has queued, sent or logged: notifications
sent right away, daily summaries and tests. Select one to read it as it went
out, with any error from the mail server.

- **Send me a test email** checks the mail server: it goes to your own address
  within 30 seconds.
- **Failed** emails are tried five times, waiting longer each time; **Retry**
  queues them again.
- With **no mail server set** (`LATTICE_SMTP_HOST` empty), nothing is sent:
  emails are kept here as **Logged**, which is how development sites work.

Reading it needs the **Read sent email** permission.

## Attachments

**Attachments** lists every file attached to a record, in every app: its name,
the record it belongs to, its size, who added it and when. Select a name to
download it; **Remove** deletes files for good. Needs the **Manage attachments**
permission, which also lets you delete anyone's files from a record's page.

The files are kept on the server in the folder `LATTICE_FILES_DIR`; back it up
with the database.

## Webhooks

**Webhooks** sends this site's events to other places as they happen: a Slack
or Teams channel, or another system. Each webhook has an address, the events it
takes (one kind, or every event) and a format:

- **CloudEvents JSON**, the standard event format, for other systems;
- **Chat message**, a short line Slack incoming webhooks and Teams workflows
  post into a channel.

Select **Add webhook**, then **Send test** to check it: the post appears under
**Deliveries** within 30 seconds with the receiver's answer. A post that fails
is tried five times, waiting longer each time; **Retry** queues it again.

Every post is **signed**. Open a webhook to see its secret: the receiver checks
the `X-Lattice-Signature` header against it, and ignores posts that do not
match. Addresses must start with `https://`.

Managing them needs the **Manage webhooks** permission.

## System

**System** shows how this site is set up:

- **Application**: its name and environment.
- **Sign-in**: the sign-in methods and session limits.
- **Counts**: users, active sessions and audit events.
- **Registered grids** and the **navigation**: every list and page of every app.

Use it to check a configuration change took effect.

## UI kit

**UI kit** shows every shared screen component, for developers and designers.
