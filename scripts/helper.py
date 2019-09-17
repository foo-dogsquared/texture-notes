# native packages
from contextlib import contextmanager
import importlib.util
import logging
from re import compile
import sqlite3
import sys

# program constants
import scripts.constants as constants


# helper functions
def sys_error_print(error, message=None, strict=False, file=sys.stderr):
    """
    Prints an error message and exit if so desired.
    :param error: The exit code from the EXIT_CODES constant. If the error from the map is not found, it'll
                  redirect to being an error with exit code 'UNKNOWN_ERROR' instead.
    :param message: The message to be printed. If there's no message, it'll use the message found on the EXIT_CODE map.
    :param strict: A boolean parameter that'll simply make the program exit after the error message has been printed.
    :param file: The file to be written off the message. By default, it'll print in the 'stderr' stream.
    :return: None
    """
    error_message = message if message is not None else constants.EXIT_CODES.get(error,
                                                                                 constants.EXIT_CODES["UNKNOWN_ERROR"])
    logging.error(error_message)
    print("\nError: {error}\n{error_message}".format(error=error, error_message=error_message), file=file)

    if strict:
        sys.exit(constants.EXIT_CODES[error])


def kebab_case(string, separator="-"):
    """
    Simply converts the string into snake_case.
    :param string: The string to be converted.
    :param separator: The separator for the resulting list of words to be joined.
    :return: str
    """
    whitespace_characters = compile(r"\s+|-+")
    invalid_characters = compile(r"[^a-zA-Z0-9]")

    word_list = whitespace_characters.split(string)
    filtered_word_list = []

    for word in word_list[:]:
        if not word:
            continue

        stripped_word = invalid_characters.sub("", word)
        if not stripped_word:
            continue

        filtered_word = stripped_word.lower()
        filtered_word_list.append(filtered_word)

    return separator.join(filtered_word_list)


def deduplicate_list(sequence, rtuple=False):
    """
    Deduplicates a list while preserving order.

    Code based in this Stack Overflow discussion (https://stackoverflow.com/a/480227).

    :param sequence: A sequence of items (list, tuple, or set).
    :type sequence: list || tuple || set

    :param rtuple: Specifies if the function should return it as a tuple instead.
    :type rtuple: bool

    :return: A list (or a tuple, if specified) of the deduplicated sequence.
    :rtype: list || tuple
    """
    seen = set()
    seen_add = seen.add

    if rtuple is True:
        return (item for item in sequence if not (item in seen or seen_add(item)))
    else:
        return [item for item in sequence if not (item in seen or seen_add(item))]


def build_prefix_array(pattern):
    """
    Returns a list of numbers (indexes) of the location where the given pattern from the text was found.
    Similar to the built-in string (`str`) function `find`), it'll return -1 when no match has found.
    :param text:
    :param pattern:
    :return: [int]
    """
    # building the prefix array
    pattern_length = len(pattern)
    prefix_array = [0] * pattern_length
    j = 0

    for i in range(1, pattern_length):
        if pattern[j] == pattern[i]:
            prefix_array[i] = j + 1
            j += 1
        else:
            j = prefix_array[j - 1]
            prefix_array[i] = j
            continue

        i += 1

    return prefix_array

def substring_search(text, pattern):
    prefix_array = build_prefix_array(pattern)

    # TODO:
    # Compare the text with pattern
    # Start by comparing the characters in the text and the pattern
    # If the character doesn't match, go back to the previous value and start the comparison
    #   in the index that the previous value pointed to
    # If it's the same, then take not of the index of the text and move to the next character

    # for index in characters:
    pass


def regex_match(string, pattern):
    regex_pattern = compile(pattern)
    return regex_pattern.search(string) is not None


# Taken from https://stackoverflow.com/a/67692
def import_config(name, location):
    spec = importlib.util.spec_from_file_location(name, location)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def initialized_db(db_path=constants.CURRENT_DIRECTORY / constants.PROFILE_DIRECTORY_NAME / constants.NOTES_DB_FILENAME):
    """
    Simply returns an initialized database. Useful if you're intending to use the same database connection throughout
    the program runtime.

    :param db_path: The name (path) of the database to be initialized.
    :type db_path: pathlib.Path

    :return: A Python SQLite3 Connection object with the initialization has already taken place.
    :rtype: sqlite3.Connection
    """
    notes_db = sqlite3.connect(db_path)
    notes_db.row_factory = sqlite3.Row

    notes_db.create_function("REGEXP", 2, regex_match)
    notes_db.create_function("SLUG", 1, kebab_case)
    notes_db.executescript(constants.NOTES_DB_SQL_SCHEMA)
    return notes_db


@contextmanager
def use_db(notes_db=None):
    """
    Simply provides a context manager for using SQLite3 databases for convenience. Usually used with `initialized_db`
    function. If no database connection was provided, it'll create and use the default connection.

    :param notes_db: The database connection object to be used. If none was provided, it'll create one with
                     `initialized_db` function and use that instead.
    :type notes_db: sqlite3.Connection

    :return: Yields a tuple similar to `init_db`
    """
    if notes_db is None:
        notes_db = initialized_db()

    try:
        cursor = notes_db.cursor()
        yield (cursor, notes_db)
        cursor.close()
        notes_db.commit()
    except sqlite3.DatabaseError as error:
        notes_db.rollback()
        raise error


@contextmanager
def init_db(db_path=constants.CURRENT_DIRECTORY / constants.PROFILE_DIRECTORY_NAME / constants.NOTES_DB_FILENAME):
    """
    Context manager for initializing and using a database right away. Take note that the database connection is
    immediately closed after.

    :param db_path: The name (path) of the database.
    :return: A tuple of a database cursor and the database connection.
    :rtype: tuple
    """
    _notes_db = initialized_db()
    with use_db(_notes_db) as (notes_cursor, notes_db):
        yield (notes_cursor, notes_db)
        notes_db.close()
