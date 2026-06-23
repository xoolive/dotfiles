# TIL: ufw

**Date:** 2026-06-09

## Background / context

Investigating why `ssh tiger` hung after tiger's hard disk was transplanted to a
new laptop. The machine responded to ping from the same network (eyjafjallajokull)
but all TCP ports timed out — port 22, 80, 443. Classic firewall DROP behaviour.
The root cause: the new hardware got a fresh OS state where **ufw defaulted to
deny-all incoming**.

## What it is

**ufw** (Uncomplicated Firewall) is the default firewall management tool on
Ubuntu/Debian. It wraps `iptables`/`nftables` with a simpler CLI. The key
behavioural detail:

- Default policy on a fresh install (or reset): **deny all incoming, allow all
  outgoing**.
- Transferring a disk to new hardware does **not** carry over the firewall state
  reliably — ufw may re-initialise to default-deny.
- DROP vs REJECT: ufw drops packets silently by default, which looks identical to
  a dead host on TCP (timeout, not "connection refused").

## Diagnosis

From another machine on the same network:

```bash
ping tiger              # responds → host is up
nc -zv -w3 tiger 22    # times out → firewall is dropping, not SSH issue
nc -zv -w3 tiger 80    # also times out → confirms it's all ports
```

All-ports timeout with ping success = firewall DROP rule, not a service problem.

## Fix

On tiger (local/physical access required):

```bash
# Check status
sudo ufw status verbose

# Allow SSH before enabling, to avoid locking yourself out
sudo ufw allow ssh        # equivalent to: sudo ufw allow 22/tcp

# Enable if not already active
sudo ufw enable

# Verify
sudo ufw status
```

If ufw wasn't the culprit, check iptables directly:

```bash
sudo iptables -L INPUT -n --line-numbers
```

## Useful commands

```bash
sudo ufw status verbose          # full rule list with default policies
sudo ufw allow ssh               # open port 22
sudo ufw allow from 134.212.0.0/16  # allow entire subnet
sudo ufw delete allow ssh        # remove a rule
sudo ufw disable                 # turn off entirely (careful)
sudo ufw reset                   # back to defaults (deny incoming)
sudo ufw reload                  # reload rules without resetting
```

## Related

- New-hardware disk transplants often reset: ufw state, Tailscale daemon (needs
  re-auth or restart), network interface names (static IP configs may break if
  bound to old interface name like `eth0` → now `enp3s0`).
- Tailscale: even with ufw fixed, tiger was offline on Tailscale (`last seen 4d
  ago`) — both issues are independent and both need fixing after a hardware swap.
