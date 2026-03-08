def is_valid_subject(sub):
    return (
        len(sub["subject_code"]) >= 6 and
        sub["credits"] > 0 and
        sub["grade"] is not None
    )