from distutils.core import setup

setup(
        name="crudster",
        version="0.0.1",
        description="Simple Motor-based document-store REST API",
        author="R. C. Thomas",
        author_email="rcthomas@lbl.gov",
        url="https://github.com/rcthomas/crudster",
        requires=["pymongo (>=3.6.0)", "tornado (>=4.5.3)", "motor (>=1.2.0)"],
        py_modules=["crudster"],
)
