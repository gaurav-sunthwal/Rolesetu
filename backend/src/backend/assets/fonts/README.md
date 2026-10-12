# Fonts used when editing resumes

When text is added to a resume and the resume's own font does not contain a
needed letter, a font drawn to the same letter widths is used instead. These are
the ones shipped with the backend, so the result is the same on every server.

| Files | Stands in for | Licence |
|---|---|---|
| `LiberationSans-*` | Arial, Helvetica | SIL Open Font License 1.1 (`LICENSE-Liberation.txt`) |
| `LiberationSerif-*` | Times New Roman | SIL Open Font License 1.1 |
| `LiberationMono-*` | Courier New | SIL Open Font License 1.1 |
| `Carlito-*` | Calibri | SIL Open Font License 1.1 (`LICENSE-Carlito.txt`) |
| `Caladea-*` | Cambria | SIL Open Font License 1.1 (`LICENSE-Caladea.txt`) |

Sources: Liberation Fonts 2.1.5 (github.com/liberationfonts/liberation-fonts);
Carlito and Caladea from github.com/google/fonts.

A real copy of the font found on the machine is preferred over these. To add
more, put the files in a folder and set `FONT_DIR`.
