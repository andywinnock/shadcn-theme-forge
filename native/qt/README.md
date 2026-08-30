# Qt/Kvantum native profile

`manage.py` derives both Graphite modes directly from `out/preview/graphite.json`.
It copies the installed `KvMojave`/`KvMojaveLight` assets into a generated,
user-local theme, remaps their SVG colors to semantic tokens, applies a 40 px
control profile where Kvantum supports minimum heights, and writes matching
qt5ct/qt6ct palettes.

The default command is a non-mutating plan (apart from repository-local output):

```sh
python native/qt/manage.py --mode dark
```

Activation, verification, and exact rollback are explicit:

```sh
python native/qt/manage.py --mode dark --apply
python native/qt/manage.py --verify
python native/qt/manage.py --rollback
```

Apply refuses to overwrite an active transaction. Verification fails closed if
any managed file changed after installation, and rollback also refuses in that
case so it cannot silently erase later user edits. No command writes to
`/usr/share` or requires root.

For Niri, export both `QT_STYLE_OVERRIDE=kvantum` and
`QT_QPA_PLATFORMTHEME=kde`. Kvantum owns component geometry, while the KDE
platform theme supplies the application palette used by KDE apps such as
Dolphin.
