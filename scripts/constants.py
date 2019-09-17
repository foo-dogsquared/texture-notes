from pathlib import Path
from string import Template

__all__ = ["PROGRAM_NAME", "SHORT_NAME",
           "CURRENT_DIRECTORY", "NOTES_DIRECTORY", "STYLE_DIRECTORY", "TEMP_DIRECTORY", "OUTPUT_DIRECTORY",
           
           "NOTE_ATTRIBUTE_NAME", "SUBJECT_ATTRIBUTE_NAME",
           "SUBCOMMAND_ATTRIBUTE_NAME", "DEFAULT_LATEX_DOC_CONFIG", "DEFAULT_LATEX_DOC_KEY_LIST",
           "DEFAULT_LATEX_MAIN_FILE_DOC_KEY_LIST", "DEFAULT_LATEX_SUBFILE_DOC_KEY_LIST", "MAIN_SUBJECT_TEX_FILENAME",
           "DEFAULT_LATEX_FILE_EXTENSION",
           "EXIT_CODES",

           # name restrictions
           "INVALID_SUBJECT_NAMES", "INVALID_NOTE_TITLES",

           # SQL-related stuff
           "NOTES_DB_SQL_SCHEMA", "NOTES_DB_FILEPATH",

           # LaTeX raw source code
           "DEFAULT_LATEX_MAIN_FILE_SOURCE_CODE", "DEFAULT_LATEX_SUBFILE_SOURCE_CODE",

           # LaTeX source code template
           "DEFAULT_LATEX_MAIN_FILE_TEMPLATE", "DEFAULT_LATEX_SUBFILE_TEMPLATE",

           # preferences
           "DEFAULT_MANAGER_PREFERENCES", "MANAGER_PREFERENCES_FILENAME",

           # SVG-related constants
           "FIGURES_DIRECTORY_NAME", "DEFAULT_NOTE_EDITOR", "DEFAULT_SVG_TEMPLATE"
           ]

# common constants
PROGRAM_NAME = "Simple Personal Lecture Manager"
SHORT_NAME = "personal-lecture-manager"

CURRENT_DIRECTORY = Path("./")

PROFILE_DIRECTORY_NAME = "texture-notes-profile"
PROFILE_DIRECTORY = CURRENT_DIRECTORY / PROFILE_DIRECTORY_NAME

NOTES_DIRECTORY_NAME = "notes"

STYLE_DIRECTORY_NAME = "styles"

OUTPUT_DIRECTORY_NAME = ".output"

TEMP_DIRECTORY_NAME = ".tmp"

NOTES_DB_FILENAME = "notes.db"

NOTE_ATTRIBUTE_NAME = "note_metalist"
SUBJECT_ATTRIBUTE_NAME = "subject_metalist"
SUBCOMMAND_ATTRIBUTE_NAME = "subcommand"

config = {
    "DEFAULT_NOTE_EDITOR": "vim",
    "FIGURES_DIRECTORY_NAME": "graphics",
    "DEFAULT_LATEXMKRC_TEMPLATE": """ensure_path( 'TEXINPUTS', '../../styles//' );""",
    "DEFAULT_LATEX_SUBFILE_SOURCE_CODE": r"""\documentclass[class=memoir, crop=false, oneside, 14pt]{standalone}

% document metadata
\author{${__author__}}
\title{${__title__}}
\date{${__date__}}

\begin{document}

\end{document}
""",
"DEFAULT_LATEX_MAIN_FILE_SOURCE_CODE": r"""\documentclass[class=memoir, crop=false, oneside, 12pt]{standalone}

% document metadata
\author{${__author__}}
\title{${__title__}}
\date{${__date__}}

\begin{document}
% Frontmatter of the class note

${__main__}

\end{document}
""",
"DEFAULT_SVG_EDITOR": "inkscape",
"DEFAULT_SVG_TEMPLATE": """<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<!-- Created with Inkscape (http://www.inkscape.org/) -->

<svg
   xmlns:dc="http://purl.org/dc/elements/1.1/"
   xmlns:cc="http://creativecommons.org/ns#"
   xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
   xmlns:svg="http://www.w3.org/2000/svg"
   xmlns="http://www.w3.org/2000/svg"
   xmlns:sodipodi="http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd"
   xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape"
   width="240mm"
   height="120mm"
   viewBox="0 0 240 120"
   version="1.1"
   id="svg8"
   inkscape:version="0.92.4 (unknown)"
   sodipodi:docname="figure.svg">
  <defs
     id="defs2" />
  <sodipodi:namedview
     id="base"
     pagecolor="#ffffff"
     bordercolor="#666666"
     borderopacity="1.0"
     inkscape:pageopacity="0.0"
     inkscape:pageshadow="2"
     inkscape:zoom="0.99437388"
     inkscape:cx="284.27627"
     inkscape:cy="182.72055"
     inkscape:document-units="mm"
     inkscape:current-layer="layer1"
     showgrid="false"
     showborder="true"
     width="200mm"
     showguides="true"
     inkscape:guide-bbox="true"
     inkscape:window-width="2520"
     inkscape:window-height="995"
     inkscape:window-x="20"
     inkscape:window-y="65"
     inkscape:window-maximized="1">
    <inkscape:grid
       type="xygrid"
       id="grid815"
       units="mm"
       spacingx="10"
       spacingy="10"
       empspacing="4"
       dotted="false" />
  </sodipodi:namedview>
  <metadata
     id="metadata5">
    <rdf:RDF>
      <cc:Work
         rdf:about="">
        <dc:format>image/svg+xml</dc:format>
        <dc:type
           rdf:resource="http://purl.org/dc/dcmitype/StillImage" />
        <dc:title />
      </cc:Work>
    </rdf:RDF>
  </metadata>
  <g
     inkscape:label="Layer 1"
     inkscape:groupmode="layer"
     id="layer1"
     transform="translate(0,-177)" />
</svg>
"""
}

DEFAULT_LATEX_DOC_KEY_LIST = ["author"]
DEFAULT_LATEX_DOC_KEY_LIST_KEYWORDS = ["date", "title"]
DEFAULT_LATEX_DOC_CONFIG = {
    "author": "Gabriel Arazas",
}

INVALID_SUBJECT_NAMES = (":all:", ":except:")
INVALID_NOTE_TITLES = (":all:", ":main:", ":union:", "stylesheets", "graphics", "readme", "main")

SUBJECT_NAME_REGEX = r"^[\w\d -]+$"

NOTES_DB_SQL_SCHEMA = rf"""/*
One thing to note here is the REGEXP function.
The version that the SQLite version to be used with this app (3.28)
doesn't have any by default and it has to be user-defined.

The REGEXP function can be found in `$PROJECT_ROOT/scripts/helper.py`
as function `regex_match`.
*/

-- enabling foreign keys since SQLite 3.x has it disabled by default
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS "subjects" (
    "id" INTEGER,
    "name" TEXT UNIQUE NOT NULL,
    "datetime_modified" DATETIME NOT NULL,
    PRIMARY KEY("id"),
    CHECK(
        TYPEOF("name") == "text" AND
        LENGTH("name") <= 128 AND
        REGEXP("name", "^[\w\d -]+") AND 
        LOWER("name") NOT IN {INVALID_SUBJECT_NAMES} AND 
        
        -- checking if the datetime is indeed in ISO format
        TYPEOF("datetime_modified") == "text" AND
        REGEXP("datetime_modified", "^\d{{4}}-\d{{2}}-\d{{2}} \d{{2}}:\d{{2}}:\d{{2}}$")
    )
);

CREATE TABLE IF NOT EXISTS "notes" (
    "id" INTEGER,
    "title" TEXT NOT NULL,
    "subject_id" INTEGER NOT NULL,
    "datetime_modified" DATETIME NOT NULL,
    PRIMARY KEY("id"),
    FOREIGN KEY("subject_id") REFERENCES "subjects"("id")
        ON DELETE CASCADE
        ON UPDATE CASCADE,
    CHECK (
        -- checking if the title is a string with less than 512 characters
        TYPEOF("title") == "text" AND
        LENGTH("title") <= 256 AND
        LOWER("title") NOT IN {INVALID_NOTE_TITLES} AND

        -- checking if the datetime is indeed in ISO format
        TYPEOF("datetime_modified") == "text" AND
        REGEXP("datetime_modified", "^\d{{4}}-\d{{2}}-\d{{2}} \d{{2}}:\d{{2}}:\d{{2}}$")
    )
);

-- creating a trigger on "notes" table which will check the uniqueness of the
-- filename of the incoming note for a subject; in other words, there may be duplicates of
-- the note with the same filename in two or more different subjects but not under
-- the same subject
CREATE TRIGGER IF NOT EXISTS unique_filename_note_check
BEFORE INSERT ON notes
BEGIN
    SELECT
    CASE
        WHEN (SELECT COUNT(title) FROM notes WHERE subject_id == NEW.subject_id AND title == NEW.title) >= 1
            THEN RAISE(FAIL, "There's already a note with the same title under the specified subject.")
    END;
END;

-- creating an index for the notes
CREATE INDEX IF NOT EXISTS notes_index ON "notes"("title", "subject_id");
"""

# TODO: Make configurable templates for main and subfiles
DEFAULT_LATEX_MAIN_FILE_DOC_KEY_LIST = []
DEFAULT_LATEX_MAIN_FILE_DOC_KEY_LIST_KEYWORDS = ["main", "preface"]
DEFAULT_LATEX_MAIN_FILE_DOC_KEY_CONFIG = {}

DEFAULT_LATEX_SUBFILE_DOC_KEY_LIST = []
DEFAULT_LATEX_SUBFILE_DOC_KEY_LIST_KEYWORDS = []
DEFAULT_LATEX_SUBFILE_DOC_KEY_CONFIG = {}

DEFAULT_LATEX_FILE_EXTENSION = ".tex"

MAIN_SUBJECT_TEX_FILENAME = "main"

# Exit codes with their generic message
EXIT_CODES = {
    "SUCCESS": "Program execution was successful.",
    "NO_SUBJECT_FOUND": "There's no subject found within the notes directory.",
    "SUBJECT_ALREADY_EXISTS": "There's a subject already found in ",
    "NO_NOTE_FOUND": "There's no note found within the notes directory.",
    "NO_LATEX_COMPILER_FOUND": "No LaTeX compiler found. If you don't have a LaTeX distribution installed on your "
                               "machine, you can install one. If you're not entirely familiar with LaTeX, I recommend "
                               "looking to this guide (https://www.ctan.org/starter) and broaden your search from "
                               "there.",
    "FILE_CONFLICT": "Certain files are detected but they are the wrong type of files (or perhaps it is a directory "
                     "instead of a file).",
    "UNSUPPORTED_PLATFORM": "Some functions of this script cannot function on certain platform. Check the code around "
                            "here and modify it yourself for now (and sorry for the inconvenience).",
    "UNKNOWN_ERROR": "An error has occurred for unknown reasons. Try to remember and replicate the steps on what "
                     "made you got this error and report it to the developer at the following GitHub repo "
                     "(https://github.com/foo-dogsquared/a-remote-repo-full-of-notes-of-things-i-do-not-know-about).",
}

# this is just for backup in case the .default_tex_template is not found
DEFAULT_LATEX_MAIN_FILE_TEMPLATE = Template(config["DEFAULT_LATEX_MAIN_FILE_SOURCE_CODE"])
DEFAULT_LATEX_SUBFILE_TEMPLATE = Template(config["DEFAULT_LATEX_SUBFILE_SOURCE_CODE"])

# constants for preferences
# TODO:
# use xdg-open (or x-www-browser) if it doesn't work for opening default files
# add support for common text (specifically LaTeX) editors
DEFAULT_MANAGER_PREFERENCES = {
    "latex-template": config["DEFAULT_LATEX_SUBFILE_SOURCE_CODE"],
    "latex-builder": "latexmk",
    "latex-engine": "pdflatex",
    "latex-engine-enable-shell-escape": True,
    "latex-engine-enable-synctex": True,
}
MANAGER_PREFERENCES_FILENAME = CURRENT_DIRECTORY / "latex-note-manager.pref.json"

# Default preferences for figures