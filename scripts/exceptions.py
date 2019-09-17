class Error(Exception):
    pass


# Base exception for profiles
class ProfileError(Error):
    def __init__(self, location):
        super().__init__()
        self.location = location


class ProfileAlreadyExistsError(ProfileError):
    def __init__(self, location):
        super().__init__(location)
        self.message = f"The location \"{location}\" has a profile already."


class ProfileDoesNotExistsError(ProfileError):
    def __init__(self, location):
        super().__init__(location)
        self.message = f"The location \"{location}\" has no profile detected."


# Base exception for subject-related errors
class SubjectError(Error):
    def __init__(self, subjects):
        super().__init__()
        self.subjects = subjects


class NoSubjectFoundError(SubjectError):
    def __init__(self, subjects):
        super().__init__(subjects)
        self.message = f"The following subject(s) is/are not found in the database: {subjects}"


class SubjectAlreadyExists(SubjectError):
    def __init__(self, subjects):
        super().__init__(subjects)
        self.message = f"The following subject/s already exist/s in the database:\n{subjects}"


class DanglingSubjectError(SubjectError):
    def __init__(self, subjects):
        super().__init__(subjects)
        self.message = f"The following subject/s is/are not found in the filesystem: \n{subjects}"


class MultipleSubjectError(Error):
    def __init__(self, subjects_not_found, dangling_subjects):
        super().__init__()
        self.subjects_not_found = subjects_not_found
        self.dangling_subjects = dangling_subjects


# Base exception for subject note-related errors
class SubjectNoteError(Error):
    def __init__(self, subject, notes):
        super().__init__()
        self.subject = subject
        self.notes = notes


class InvalidNoteTitleError(SubjectNoteError):
    def __init__(self, subject, notes):
        super().__init__(subject, notes)
        self.message = f"The following notes under subject '{subject}' has invalid title: \n{notes}"


class NoSubjectNoteFoundError(SubjectNoteError):
    def __init__(self, subject, notes):
        super().__init__(subject, notes)
        self.message = f"The following notes under subject '{subject}' is not found in the database:\n{notes}"


class SubjectNoteAlreadyExistError(SubjectNoteError):
    def __init__(self, subject, notes):
        super().__init__(subject, notes)
        self.message = f"The note with the title '{notes}' under"


class DanglingSubjectNoteFoundError(SubjectNoteError):
    def __init__(self, subject, notes):
        super().__init__(subject, notes)
        self.message = f"The following notes under subject '{subject}' is not found in the filesystem:\n{notes}"


class MultipleSubjectNoteError(Error):
    def __init__(self, subject, missing_notes, dangling_notes):
        super().__init__()
        self.subject = subject
        self.missing_notes = missing_notes
        self.dangling_notes = dangling_notes


class MultipleSubjectNoteSetError(Error):
    def __init__(self, subject_notes_set):
        super().__init__()
        self.subject_notes_set = subject_notes_set
