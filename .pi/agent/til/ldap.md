# TIL: ldap

**Date:** 2026-06-21

## Background / context

Apple Contacts could not find people through the LDAP account for `gaia.onecert.fr`, while the local `ldap` script worked, e.g. `ldap demange` returned the expected ONERA person record. After enabling the account in Contacts, searches returned three entries for the same query, but only one was the actual person contact.

## What it is

LDAP, Lightweight Directory Access Protocol, is a protocol for querying directory services: people, groups, organizational units, devices, and other structured records. Queries are run against a server, a search base DN, a scope, and a filter.

Practical pieces that mattered here:

- **Server URI:** `ldap://gaia.onecert.fr`
- **Base DN:** where the search starts, e.g. `dc=onera,dc=fr` or narrower `ou=people,dc=onera,dc=fr`
- **Scope:** how far below the base to search. `base` only searches the base object itself; `subtree` searches below it.
- **Filter:** LDAP expression such as `(sn=*demange*)` or a compound person lookup.
- **SSL/LDAPS:** `ldaps://...` is not the same as plain `ldap://...`; this server worked over plain LDAP, not LDAPS.

## Key finding or fix

The local script worked because it used plain LDAP, a useful base DN, and subtree search:

- server: `ldap://gaia.onecert.fr`
- bind: anonymous/simple auto bind
- base: `dc=onera,dc=fr`
- scope: subtree

Apple Contacts was misconfigured with an empty search base and `base` scope, which effectively searched only the root object and returned no people. LDAPS also failed for this server.

Initial Contacts fix:

- Server: `gaia.onecert.fr`
- Use SSL: off
- Search base: `dc=onera,dc=fr`
- Scope: `Subtree`

Then Contacts found too much: Wi-Fi/MIP entries plus the real person. The better fix is to narrow the base to people only:

- **Search base:** `ou=people,dc=onera,dc=fr`
- **Scope:** `Subtree`
- **SSL:** off
- **Server:** `gaia.onecert.fr`

This returns only the real contact for `demange`: `Julien Demange-Chryst`.

## Commands / examples

Local script location and behavior:

```sh
which ldap
# /Users/xo/Documents/scripts/ldap

ldap demange
# [{"telephoneNumber": "52811", "l": "Toulouse", "employeeNumber": "108017", "uid": "jdemange", "mail": "julien.demange-chryst@onera.fr", "cn": "Julien Demange-Chryst", ...}]
```

Relevant script settings:

```python
server = ldap3.Server("ldap://gaia.onecert.fr")
conn = ldap3.Connection(server, auto_bind=True)
conn.search(
    "dc=onera,dc=fr",
    "(&(objectClass=*)(uid=*)(|(sn=*{query}*)(mail=*{query}*)(uid=*{query}*)(telephoneNumber=*{query}*)))",
    attributes=["uid", "employeeNumber", "cn", "mail", "l", "telephoneNumber", "roomNumber", "ou", "createTimestamp"],
)
```

Plain LDAP with empty base and base scope: succeeds technically, but finds no person entries.

```sh
ldapsearch -x -H ldap://gaia.onecert.fr \
  -b '' \
  -s base \
  '(sn=*demange*)' cn
```

Plain LDAP with broad ONERA base and subtree scope: finds multiple entries, including non-person records.

```sh
ldapsearch -x -H ldap://gaia.onecert.fr \
  -b dc=onera,dc=fr \
  -s sub \
  '(sn=*demange*)' cn sn givenName mail uid telephoneNumber
```

Observed broad-base duplicates included:

```text
cn=demange,ou=wifi-test,o=mip,dc=onera,dc=fr
uid=jdemange,ou=people,dc=onera,dc=fr
cn=jdemange,ou=wifi,o=mip,dc=onera,dc=fr
```

Narrow people-only base: the useful Contacts configuration.

```sh
ldapsearch -x -H ldap://gaia.onecert.fr \
  -b ou=people,dc=onera,dc=fr \
  -s sub \
  '(sn=*demange*)' cn sn givenName mail uid telephoneNumber o ou
```

Expected result:

```text
dn: uid=jdemange,ou=people,dc=onera,dc=fr
uid: jdemange
cn: Julien Demange-Chryst
givenName: Julien
sn: Demange-Chryst
mail: julien.demange-chryst@onera.fr
o: ONERA
ou: DTIS/RIME
telephoneNumber: 52811
```

LDAPS test failed, so leave SSL disabled in Contacts:

```sh
ldapsearch -x -H ldaps://gaia.onecert.fr \
  -b dc=onera,dc=fr \
  -s sub \
  '(sn=*demange*)' cn
# ldap_sasl_bind(SIMPLE): Can't contact LDAP server (-1)
```
