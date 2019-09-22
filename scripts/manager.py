# native packages
from datetime import date
from functools import reduce
import logging
from multiprocessing import cpu_count
from os import chdir, getcwd
from os.path import relpath
from shutil import copy, copytree, rmtree
from pathlib import Path
from platform import system
import sqlite3
from string import Template
from subprocess import run

# custom packages
import scripts.constants as constants
import scripts.exceptions as exceptions
from .helper import kebab_case, initialized_db, use_db, regex_match, deduplicate_list

"""
All of the note functions accepts a metalist of notes with the subject as the first item in each
individual list.

[[SUBJECT_1, TITLE_1.1, TITLE_1.2, ..., TITLE_1.x], [SUBJECT_2, TITLE_2.1, TITLE_2.2, ..., TITLE_2.y], ...]

Example:
    - add_note([["Calculus", "Precalculus Review", "Introduction to Limits"], 
                ["Physics", "Introduction to Electronics"]])
    - remove_note([["Calculus", "Note that I don't need to"]])
    - compile_note([["Calculus", ":all:"], ["Physics", "A note that I need to compile right now", 
                    "Physics 2: Electric Boogaloo"]])

"""


def create_symbolic_link(_link, _target, filename):
    """Simply creates a relative symbolic link through the shell. Cross-platform support is down to a minimum
    so expect some bugs to pop up often.

    :param _link: The path to be linked.
    :type _link: Path

    :param _target: The target or the destination of the symbolic link to be created.
    :type _target: Path

    :return: The results from a `subprocess.run` invocation. For more information, visit the following page
             (https://docs.python.org/3/library/subprocess.html#subprocess.run).
    """
    os_platform = system()
    symbolic_link_creation_process = None
    link = relpath(_link, _target)
    target = _target

    if os_platform == "Windows":
        symbolic_link_creation_process = run(["ln", "--symbolic", link, target / filename])
    elif os_platform == "Linux":
        symbolic_link_creation_process = run(["ln", "--symbolic", link, target / filename])
    else:
        symbolic_link_creation_process = run(["ln", "--symbolic", link, filename])

    return symbolic_link_creation_process


def convert_subject_query_to_dictionary(subject_query, metadata=None):
        subject_query = dict(subject_query)
        subject_query["slug"] = kebab_case(subject_query["name"])
        subject_query["path"] = metadata["notes"] / subject_query["slug"]
        return subject_query


def get_profile(location=constants.CURRENT_DIRECTORY):
    """
    Gets a profile and return the appropriate data.

    :param location:
    :return:
    """
    location_path = Path(location)
    profile = location_path / constants.PROFILE_DIRECTORY_NAME
    if profile.exists() is False:
        raise exceptions.ProfileDoesNotExistsError(location)

    notes = profile / constants.NOTES_DIRECTORY_NAME
    db = initialized_db(notes / constants.NOTES_DB_FILENAME)

    return {
        "profile": profile,
        "notes": notes,
        "styles": profile / constants.STYLE_DIRECTORY_NAME,
        "db": db,
    }


def create_profile(location=constants.CURRENT_DIRECTORY):
    """
    Create a TexTure Notes profile.

    :param location: The location where the profile will be created.
    :type location: str

    :return: dict
    """
    location_path = Path(location)
    profile = location_path / constants.PROFILE_DIRECTORY_NAME
    if profile.exists() is True or profile.is_symlink() is True:
        raise exceptions.ProfileAlreadyExistsError(location)

    profile.mkdir()

    latexmkrc_file = profile / "latexmkrc"
    latexmkrc_file.touch()
    with open(latexmkrc_file, "w") as latexmkrc:
        latexmkrc.write(constants.config["DEFAULT_LATEXMKRC_TEMPLATE"])

    styles = profile / constants.STYLE_DIRECTORY_NAME
    styles.mkdir()

    notes = profile / constants.NOTES_DIRECTORY_NAME
    notes.mkdir()

    notes_db = initialized_db(notes / constants.NOTES_DB_FILENAME)

    return {
        "profile": profile,
        "notes": notes,
        "styles": styles,
        "db": notes_db,
    }


def get_subject(subject, delete_in_db=True, metadata=None):
    """Get a subject if it exists in the database and automatically handles the case if
    the directory is deleted while the subject is found in the database.

    :param subject: The subject to be searched.
    :type subject: str

    :param delete_in_db: Simply deletes the subject entry in database if it's found to be a dangling subject. It is
                         enabled by default.
    :type delete_in_db: bool

    :param db: The database connection to be used.
    :type db: sqlite3.Connection

    :return: A dictionary of the subject query from the SQLite database along with an instance of Path of their
             filepath.
    :rtype: dict

    :raises NoSubjectFoundError: Raised if the subject is not found in the database.
    :raises DanglingSubjectError: Raised if the subject is found in the database but not found in the filesystem.
    """
    with use_db(metadata["db"]) as (notes_cursor, notes_db):
        subject_slug = kebab_case(subject)

        notes_cursor.execute("SELECT id, name, datetime_modified FROM subjects WHERE name == :name;",
                             {"name": subject})

        subject_query = notes_cursor.fetchone()
        if subject_query is None:
            raise exceptions.NoSubjectFoundError(subject)

        subject_value = convert_subject_query_to_dictionary(subject_query, metadata=metadata)

        if subject_value["path"].is_dir() is False:
            if delete_in_db is True:
                notes_cursor.execute("DELETE FROM subjects WHERE id == :subject_id;", {"subject_id": subject_query["id"]})
                notes_db.commit()
            raise exceptions.DanglingSubjectError(subject_value)

        return subject_value


def get_subject_by_id(id, delete_in_db=True, metadata=None):
    with use_db(metadata["db"]) as (notes_cursor, notes_db):
        notes_cursor.execute("SELECT id, name, datetime_modified FROM subjects WHERE "
                            "id == :id;", {"id": id})
        
        subject_query = notes_cursor.fetchone()
        if subject_query is None:
            raise exceptions.NoSubjectFoundError(id)
        
        subject_query = convert_subject_query_to_dictionary(subject_query, metadata=metadata)
        
        if subject_query["path"].is_dir() is False:
            if delete_in_db is True:
                notes_cursor.execute("DELETE FROM subjects WHERE id == :subject_id;", {"subject_id": subject_query["id"]})
                notes_db.commit()
            raise exceptions.DanglingSubjectError(subject_query["name"])
        
        return subject_query


def convert_note_query_to_dictionary(note_query, subject_query):
    note = dict(note_query)
    note["subject"] = subject_query["name"]
    note["slug"] = kebab_case(note["title"])
    note["path"] = subject_query["path"] / (note["slug"] + ".tex")
    note["subject_path"] = subject_query["path"]
    return note


def get_subjects(*subjects, **kwargs):
    """
    Retrieves a list of subjects. Query data results are similar to the `get_subject` function.

    :param subjects: A list of subjects to be searched.
    :type subjects: list[str]

    :keyword strict: Indicates that the function will raise an exception if there are missing and dangling subjects.
                     It is disabled by default.

    :keyword delete_in_db: Deletes the subject entry in the database if it's found to be a dangling subject. It is
                           enabled by default.

    :return: A tuple that is made up of three items: a list of dictionaries similar to the data returned
             from `get_subject` function, a list of subjects that are not found, and a list of dangling subjects
             with their data similar to the first list.
    :rtype: tuple[list]

    :raises MultipleSubjectError: Raises an exception if the function is in strict mode and there's invalid and
                                 dangling subjects.
    """

    db = kwargs.pop("db", None)
    profile_metadata = kwargs.pop("metadata")

    with use_db(profile_metadata["db"]) as (notes_cursor, notes_db):
        # this will eventually be the list for subjects that are not found
        subjects_set = deduplicate_list(subjects)

        subject_set_valid_sql_string = "(" + ", ".join(str(f"'{subject}'") for subject in subjects_set) + ")"
        notes_cursor.execute(f"SELECT id, name, datetime_modified FROM subjects WHERE name "
                             f"IN {subject_set_valid_sql_string};")

        subjects_query = notes_cursor.fetchall()

        # getting the valid keyword arguments handling for this function
        strict = kwargs.pop("strict", False)
        delete_in_db = kwargs.pop("delete_in_db", True)

        # this list will first receive the index of the dangling notes before the note dictionaries
        dangling_subjects = []

        for (index, subject) in enumerate(subjects_query):
            subject = convert_subject_query_to_dictionary(subject, metadata=profile_metadata)
            subjects_query[index] = subject

            # remove the subjects that are found in the set
            # the remaining subject names are the one that is not found in the database
            try:
                subject_index = subjects_set.index(subject["name"])
                subjects_set.pop(subject_index)
            except ValueError:
                continue

            if subject["path"].is_dir() is False:
                dangling_subjects.append(index)

                if delete_in_db is True:
                    notes_cursor.execute("DELETE FROM subjects WHERE id == :subject_id;", {"subject_id": subject["id"]})
                    notes_db.commit()
                continue

        dangling_subjects[:] = [subjects_query.pop(index) for index in dangling_subjects]

        if (len(subjects_set) > 0 or len(dangling_subjects) > 0) or len(subjects_query) > 0:
            if strict is True:
                raise exceptions.MultipleSubjectError(subjects_set, dangling_subjects)

        return subjects_query, subjects_set, dangling_subjects


def get_all_subjects(sort_by=None, strict=False, delete_in_db=True, metadata=None):
    """Retrieve all of the subjects from the notes database.

    :param sort_by: Lists note in a particular order. Only accepts a limited range of keywords. Such keywords
                    include "id", "name", and "date". Any invalid choices are not sorted in any way.
    :type sort_by: str

    :param strict: Indicates that the function will raise an exception if there are missing and/or dangling subjects.
                   It is disabled by default.
    :type strict: bool

    :param delete_in_db: If enabled, let the function handle dangling subjects simply by deleting their entry in the
                       database. It is enabled by default.
    :type delete_in_db: bool

    :param db: The database connection to be used. If none was provided, it'll use the default connection.
    :type db: sqlite3.Connection

    :return: A tuple made up of the following: a list of dictionaries similar of structure
            from "get_subject" function and a list of dangling subjects.
    :rtype: tuple[list]

    :raises DanglingSubjectError: When the function is in strict mode and there are dangling subjects
                                  found in the database.
    """
    with use_db(metadata["db"]) as (notes_cursor, notes_db):
        select_all_notes_sql_statement = "SELECT id, name, datetime_modified FROM subjects "

        if sort_by == "id":
            select_all_notes_sql_statement += "ORDER BY id;"
        elif sort_by == "name":
            select_all_notes_sql_statement += "ORDER BY name;"
        elif sort_by == "date":
            select_all_notes_sql_statement += "ORDER BY datetime_modified;"

        notes_cursor.execute(select_all_notes_sql_statement)

        # take note that this list will receive list indices before the metadata
        dangled_subjects = []

        subjects_query = notes_cursor.fetchall()
        for (index, _subject) in enumerate(subjects_query):
            subject = convert_subject_query_to_dictionary(_subject, metadata=metadata)
            subjects_query[index] = subject

            if subject["path"].is_dir() is False:
                dangled_subjects.append(index)

                if delete_in_db is True:
                    notes_cursor.execute("DELETE FROM subjects WHERE id == :subject_id;",
                                        {"subject_id": subject["id"]})
                    notes_db.commit()
                continue

        # putting all of the dangling subjects in the array
        dangled_subjects[:] = [subjects_query.pop(index) for index in dangled_subjects]

        if len(dangled_subjects) > 0 and strict is True:
            raise exceptions.DanglingSubjectError(dangled_subjects)

        return subjects_query, dangled_subjects


def get_subject_note(subject, note, delete_in_db=True, metadata=None):
    """
    Simply finds the note from the given subject.
    
    :param subject: The subject from where the note to be retrieved.

    :type subject: str

    :param note: The title of the note to be searched.
    :type note: str

    :param delete_in_db: If given true, let the function delete the dangling subject entry in the database before
                         raises an exception. It is enabled by default.
    :type delete_in_db: bool

    :param db: The SQLite3 database connection to be used. If none was given, it'll create and use the default
               connection.
    :type db: sqlite3.Connection

    :return: A dictionary of the subject note as retrieved from the SQLite database along with the path
              assigned in the key "path".
    :rtype: dict

    :raises NoSubjectFoundError: When the subject is not found in the database.
    :raises DanglingSubjectError: When the subject is found in the database but not in the filesystem.
    :raises NoSubjectNoteFoundError: When the subject note is not found in the database.
    :raises DanglingSubjectNoteError: When the subject is found in the database but the corresponding file is missing.
    """
    try:
        subject_query = get_subject(subject, delete_in_db=delete_in_db, metadata=metadata)
    except (exceptions.NoSubjectFoundError, exceptions.DanglingSubjectError) as error:
        raise error

    with use_db(metadata["db"]) as (notes_cursor, notes_db):
        note = note.strip()

        note_query_arguments = {"subject_id": subject_query["id"], "title": note}
        
        notes_cursor.execute("SELECT id, subject_id, title, datetime_modified FROM notes WHERE "
                            "subject_id == :subject_id AND title == :title;", note_query_arguments)
        note_query = notes_cursor.fetchone()

        if note_query is None:
            raise exceptions.NoSubjectNoteFoundError(subject, [note])

        note_value = convert_note_query_to_dictionary(note_query, subject_query)

        if note_value["path"].is_file() is False:
            if delete_in_db:
                notes_cursor.execute("DELETE FROM notes WHERE id == :note_id;", {"note_id": note_query["id"]})
                notes_db.commit()
            raise exceptions.DanglingSubjectNoteFoundError(subject, [note_value])

        return note_value


def get_subject_note_by_id(id, delete_in_db=True, metadata=None):
    try:
        int(id)
    except ValueError:
        raise ValueError("Given ID does not convert to an integer.")
    
    with use_db(metadata["db"]) as (notes_cursor, notes_db):
        notes_cursor.execute("SELECT id, subject_id, title, datetime_modified FROM notes WHERE "
                            "id == :id;", {"id": id})
        note_query = notes_cursor.fetchone()

        if note_query is None:
            raise exceptions.NoSubjectNoteFoundError(None, id)
        
        try:
            subject_query = get_subject_by_id(note_query["subject_id"], delete_in_db=delete_in_db, metadata=metadata)
        except (exceptions.NoSubjectFoundError, exceptions.DanglingSubjectError) as error:
            raise error

        note_query = convert_note_query_to_dictionary(note_query, subject_query)
        
        if note_query["path"].is_file() is False:
            if delete_in_db is True:
                if delete_in_db:
                        notes_cursor.execute("DELETE FROM notes WHERE id == :note_id;", {"note_id": note_query["id"]})
                        notes_db.commit()
                raise exceptions.DanglingSubjectNoteFoundError(subject, [note_query])

        return note_query

def get_all_subject_notes(subject, sort_by=None, strict=False, delete_in_db=True, metadata=None):
    """Retrieve all notes under the given subject.

    :param subject: The subject to be retrieve all of the notes.
    :type subject: str

    :param sort_by: The column to be based how the results should be ordered. Choices include
                    "title", "id", and "date". Any invalid choices are not sorted in any way.
    :type sort_by: str

    :param strict: Indicates if the program should raise if there's dangling subject/notes in the database.
    :type strict: bool

    :param delete_in_db: Indicates if the function should delete dangling subject/notes entry in the database.
    :type delete_in_db: bool

    :param db: The database connection to be used. If none is given, it'll create and use the default connection.
    :type db: sqlite3.Connection

    :return: A tuple made up of two items: a list of valid subject notes and a list of dangling items.
    :rtype: tuple[list]

    :raises NoSubjectFoundError: When the given subject is not found in the database.
    :raises DanglingSubjectError: When the given subject is found to be dangling.
    :raises DanglingSubjectNotesError: When there are dangling subjects note found and the function is set to strict mode.
    """
    try:
        subject = subject.strip(" -")
        subject_query = get_subject(subject, delete_in_db=True, metadata=metadata)
    except (exceptions.NoSubjectFoundError, exceptions.DanglingSubjectError) as error:
        raise error

    with use_db(metadata["db"]) as (notes_cursor, notes_db):
        sql_statement = "SELECT id, title, subject_id, datetime_modified FROM notes " \
                        "WHERE subject_id == :subject_id "

        if sort_by == "id":
            sql_statement += "ORDER BY id"
        elif sort_by == "title":
            sql_statement += "ORDER BY title"
        elif sort_by == "date":
            sql_statement += "ORDER BY datetime_modified"

        # getting the subject notes
        notes_cursor.execute(sql_statement, {"subject_id": subject_query["id"]})

        notes_query = notes_cursor.fetchall()
        dangling_notes = []

        for (index, _note) in enumerate(notes_query):
            note = convert_note_query_to_dictionary(_note, subject_query)
            notes_query[index] = note

            if note["path"].is_file() is False:
                if delete_in_db:
                    notes_cursor.execute("DELETE FROM notes WHERE id == :note_id;", {"note_id": _note["note_id"]})
                    notes_db.commit()

                dangling_notes.append(index)
                continue

        dangling_notes[:] = [notes_query.pop(index) for index in dangling_notes]

        if len(dangling_notes) > 0 and strict is True:
            raise exceptions.DanglingSubjectNoteFoundError(dangling_notes)

        return notes_query, dangling_notes


def create_subject(subject, metadata=None):
    """Formally adds the given subject into the binder. It will be added into the database and automate
    the creation of the template needed for the subject.

    :param subject: The subject to be added.
    :type subject: str

    :param db: The database connection to be used. If no database connection given, it'll get one within the `use_db`
               function.
    :type db: sqlite3.Connection

    :return: The newly added subject data similar to the data from `get_subject` function.
    :rtype: dict

    :raises ValueError: When the given subject name is not valid.
    :raises SubjectAlreadyExistsError: When the given subject already exists in the database.
    """
    subject = subject.strip(" -")

    if subject.lower() in constants.INVALID_SUBJECT_NAMES is True:
        raise ValueError(f"Given name is one of the keywords.")
    elif regex_match(subject, constants.SUBJECT_NAME_REGEX) is False:
        raise ValueError(f"Given name contains invalid characters.")
    elif regex_match(subject, "^\d+$") is True:
        raise ValueError(f"Given name contains invalid characters")

    with use_db(metadata["db"]) as (notes_cursor, notes_db):
        subject_slug = kebab_case(subject)
        try:
            notes_cursor.execute("INSERT INTO subjects (name, datetime_modified) VALUES (:name, DATETIME());",
                             {"name": subject})
            notes_db.commit()
        except sqlite3.IntegrityError as error:
            raise exceptions.SubjectAlreadyExists(subject)
        except sqlite3.Error as error:
            raise error

        subject_folder_path = metadata["notes"] / subject_slug

        # creating the folder for the subject
        subject_folder_path.mkdir(exist_ok=True)

        # creating the `graphics/` folder in the subject directory
        subject_graphics_folder_path = subject_folder_path / "graphics/"
        subject_graphics_folder_path.mkdir(exist_ok=True)

        # creating the symbolic link for the stylesheet directory which should only
        # be two levels up in the root directory
        latexmk_symbolic_link_path = subject_folder_path / "latexmkrc"

        if latexmk_symbolic_link_path.is_file():
            latexmk_symbolic_link_path.unlink()

        symbolic_link_creation_process = create_symbolic_link(metadata["profile"] / "latexmkrc", subject_folder_path, "latexmkrc")

        bibfile = subject_folder_path / "ref.bib"
        bibfile.touch()

        return get_subject(subject, metadata=metadata)


def create_subject_note(subject, note_title, force=False, metadata=None):
    """Create a subject note in the binder.

    :param subject: The subject where the note will belong.
    :type subject: str

    :param note_title: The title of the note.
    :type note_title: str

    :param force: Force insertion of the file, if it already exist in the filesystem. Otherwise, the already existing
                  file is going to be the file associated with the note.
    :type force: bool

    :param db: The database connection to be used. If none was provided, the default connection will be used.
    :type db: sqlite3.Connection

    :return: A data from the `get_subject_note` of the newly inserted note.
    :rtype: dict

    :raises NoSubjectFoundError: When the subject given doesn't exist in the database.
    :raises DanglingSubjectError: When the subject is found to be dangling.
    :raises SubjectNoteAlreadyExistError: When the note under the given subject already exists in the database.
    :raises ValueError: When the note given is invalid (either it is one of the keywords, invalid characters,
                        or length is not at range.
    :raises sqlite3.Error: When the SQLite3 goes something wrong.
    """
    # making sure the note doesn't exists before continuing
    try:
        note = get_subject_note(subject, note_title, delete_in_db=True, metadata=metadata)
        raise exceptions.SubjectNoteAlreadyExistError(subject, [note])
    except (exceptions.NoSubjectFoundError, exceptions.DanglingSubjectError) as error:
        raise error
    except (exceptions.NoSubjectNoteFoundError, exceptions.DanglingSubjectNoteFoundError) as error:
        pass
    except exceptions.SubjectNoteAlreadyExistError as error:
        raise error

    if note_title in constants.INVALID_NOTE_TITLES or len(note_title) > 256:
        raise ValueError(subject, note_title)
    if regex_match(note_title, "^\d+$") is True:
        raise ValueError(subject, note_title)

    note_title = note_title.strip()
    with use_db(metadata["db"]) as (notes_cursor, notes_db):
        try:
            notes_cursor.execute("INSERT INTO notes (title, subject_id, datetime_modified) VALUES "
                                 "(:title, (SELECT id FROM subjects WHERE name == :subject), "
                                 "DATETIME());",
                                 {"title": note_title, "subject": subject})
        except sqlite3.DatabaseError as error:
            raise error

        subject_query = get_subject(subject, delete_in_db=True, metadata=metadata)

        note_title_slug = kebab_case(note_title)
        note_title_filepath = subject_query["path"] / (note_title_slug + ".tex")

        if note_title_filepath.is_file() is False or force is True:
            note_title_filepath.touch(exist_ok=True)

            with note_title_filepath.open(mode="w") as note_file:
                today = date.today()

                custom_config = {}
                for config_key, config_value in constants.DEFAULT_LATEX_DOC_CONFIG.items():
                    custom_config[f"__{config_key}__"] = config_value

                latex_subfile_source_template = Template(constants.config["DEFAULT_LATEX_SUBFILE_SOURCE_CODE"])
                note_file.write(
                    latex_subfile_source_template.safe_substitute(__date__=today.strftime("%B %d, %Y"),
                                                                             __title__=note_title,
                                                                             **custom_config)
                )

    return get_subject_note(subject, note_title, metadata=metadata)


def create_main_note(subject, _preface=None, strict=False, metadata=None,  **kwargs):
    try:
        subject_query = get_subject(subject, metadata=metadata)
    except (exceptions.DanglingSubjectError, exceptions.NoSubjectFoundError) as error:
        raise error

    try:
        subject_notes_query = get_all_subject_notes(subject, strict=strict, delete_in_db=True, metadata=metadata)
    except exceptions.DanglingSubjectNoteFoundError as error:
        raise error

    custom_config = {}
    if _preface is not None:
        preface = f"\\chapter{{Preface}}\n{Template(_preface).safe_substitute(__subject__=subject)}\n\\newpage\n"
    else:
        preface_file = subject_query["path"] / "README.txt"
        preface = ""

        if preface_file.is_file() is True:
            with preface_file.open(mode="r") as subject_preface_file:
                preface_text = subject_preface_file.read()
                preface = f"\\chapter{{Preface}}\n" \
                          f"{Template(preface_text).safe_substitute(__subject__=subject)}\n\\newpage\n"

    main_content = ""
    today = date.today()

    for note in subject_notes_query[0]:
        main_content += f"\\part{{{note['title']}}}\n\\inputchilddocument{{{note['slug']}}}\n\n"

    for key in constants.DEFAULT_LATEX_DOC_KEY_LIST:
        if key in constants.DEFAULT_LATEX_DOC_KEY_LIST_KEYWORDS:
            continue

        _value = constants.DEFAULT_LATEX_DOC_CONFIG.get(key, "")
        value = Template(_value).safe_substitute(__subject__=subject, __date__=today.strftime("%B %d, %Y"))
        custom_config[f"__{key}__"] = value

    for key in constants.DEFAULT_LATEX_MAIN_FILE_DOC_KEY_LIST:
        if key in constants.DEFAULT_LATEX_MAIN_FILE_DOC_KEY_LIST_KEYWORDS:
            continue

        _value = constants.DEFAULT_LATEX_MAIN_FILE_DOC_KEY_CONFIG.get(key, "")
        value = Template(_value).safe_substitute(__subject__=subject, __date__=today.strftime("%B %d, %Y"))
        custom_config[f"__{key}__"] = value

    main_note_filepath = subject_query["path"] / f"{constants.MAIN_SUBJECT_TEX_FILENAME}.tex"
    main_note_filepath.touch(exist_ok=True)
    with main_note_filepath.open(mode="w") as main_note:
        main_note.write(
            constants.config["DEFAULT_LATEX_MAIN_FILE_TEMPLATE"].safe_substitute(__date__=today.strftime("%B %d, %Y"),
                                                                       __title__=subject,
                                                                       __preface__=preface,
                                                                       __main__=main_content,
                                                                       **custom_config)
        )


def create_subject_graphics(subject, *figures, **kwargs):
    subject = subject.strip(" -")
    subject_query = get_subject(subject)

    if subject_query is None:
        return None

    # creating the figures
    for figure in figures:
        svg_filename = kebab_case(figure)
        svg_figure_path = subject_query["path"] / constants.config["FIGURES_DIRECTORY_NAME"] / (svg_filename + ".svg")
        svg_figure_path.touch(exist_ok=True)

        with svg_figure_path.open(mode="w") as svg_figure:
            svg_figure.write(constants.config["DEFAULT_SVG_TEMPLATE"])


def remove_subject(subject, delete, metadata=None):
    """Simply removes the subject from the binder.

    :param subject: The subject to be removed.
    :type subject: str

    :param delete: Specifies if the program deletes the subject folder in the filesystem as well.
    :type delete: bool

    :param db: The database connection to be used.
    :type db: sqlite3.Connection

    :return: The data of the subject being deleted if found in the database.
    :rtype: dict

    :raises NoSubjectFoundError: When the subject doesn't exist in the database.
    """
    try:
        subject = subject.strip(" -")
        subject_query = get_subject(subject, delete_in_db=True, metadata=metadata)
    except (exceptions.NoSubjectFoundError, exceptions.DanglingSubjectError) as error:
        raise error

    with use_db(metadata["db"]) as (notes_cursor, notes_db):
        notes_cursor.execute("DELETE FROM subjects WHERE id == :subject_id;",
                         {"subject_id": subject_query["id"]})

    if delete:
        rmtree(subject_query["path"], ignore_errors=True)

    return subject_query


def remove_all_subjects(delete=False, metadata=None):
    """Simply removes all subject in the binder.

    :param delete: If given true, deletes the subject in disk.
    :type delete: bool

    :param db: The database connection to be used. If none was provided, it'll create and use the default connection.
    :type db: sqlite3.Connection

    :return: The data of the subjects being deleted.
    :rtype: int
    """
    subjects_query = get_all_subjects(metadata=metadata)

    for subject in subjects_query[0]:
        remove_subject(subject["name"], delete=delete, metadata=metadata)

    return subjects_query


def remove_subject_note(subject, note, delete_on_disk=False, metadata=None):
    """ Remove a single subject note in the binder.

    :param subject: The name of the subject where the note belongs.
    :type subject: str

    :param note: The title of the note to be removed.
    :type note: str

    :param delete_on_disk: If enabled, simply removes the associated file of the note from the disk.
    :type delete_on_disk: bool

    :param db: The database connection to be used. If none was provided, it'll use the default connection.
    :type db: sqlite3.Connection

    :return: The data of the removed subject note.
    :rtype: dict

    :raises NoSubjectFoundError: When the subject is not found in the database.
    :raises DanglingSubjectError: When the subject is not found in the filesystem.
    :raises NoSubjectNoteFoundError: When the subject note is not found in the database.
    :raises DanglingSubjectNoteError: When the subject is found in the database but the corresponding file is missing.
    """
    try:
        note_query = get_subject_note(subject, note, delete_in_db=True, metadata=metadata)
    except exceptions.Error as error:
        raise error

    with use_db(metadata["db"]) as (notes_cursor, notes_db):
        notes_cursor.execute("DELETE FROM notes WHERE id == :note_id;", {"note_id": note_query["id"]})

        if delete_on_disk is True:
            note_query["path"].unlink()

    return note_query


def remove_all_subject_notes(subject, delete_on_disk=False, metadata=None):
    notes_query = get_all_subject_notes(subject, delete_in_db=True, metadata=metadata)

    for note in notes_query[0]:
        remove_subject_note(subject, note["title"], delete_on_disk=delete_on_disk, metadata=metadata)

    return notes_query


def update_subject(subject, new_subject, delete_in_db=True, metadata=None):
    pass


def update_subject_note(subject, note_title, new_note_title, delete_in_db=True, metadata=None):
    pass

