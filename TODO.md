
## MDOORS

This project should be a systems engineering/requirements management tool, focusing on the following:
- All requirements stored in a simple, version control friendly, textual format.
- Easily output full or partial requirements database in easy to use formats
- Generate high quality html documents of requirements and easily served web tools for searching them.

The project should be written entirely in python, with few dependencies, although some dependencies are fine
when they are extremely useful. A virtual environment must be used for dependencies. The project must work on
linux and windows.

Requirements are stored in the following way:
- Each individual requirement is a markdown file with a json frontmatter containing metadata. The name of the file is the requirement ID.
- Requirements in the same folder will be combined into a single document.
  - Order of requirements with in the file should be determined by the last substring before the file extension. For example, the files:
    - req-1.md
    - req-1.1.2.md
    - req-1.1.1.md
    Would be ordered as:
    1. req-1.md
    2. req-1.1.1.md
    3. req-1.1.2.md
    within a page. In general, more dots = deeper nested
- Any document can have a subfolder within it, which will be a "child" document. Every document has 0 or 1 parent and 0 or more children.
- All documents are children or grand-children of a "root" document.
- The root folder should contain a req-template.json file which is a set of default json fields a new requirement is populated with.
- any requirement can reference another using [[$REQID]] syntax. This should be captured in metadata. 
  - For example, if req-a contains [[req-b]], then req-a has a `"link-to": [ "req-b" ]` attribute and req-b has a `"link-from": [ "req-a" ]` attribute.

MDOORS needs a cli that can manipulate and use the above file format:
- `mdoors req add $REQID` add new requirement, taking ID as input it will make a blank markdown file in the appropriate folder populated with req-template.json frontmatter
- `mdoors export csv $DOC` export $DOC as a csv with all its child requirements and their associated metadata. $DOC is a path to a folder
- `mdoors export sqlite $DOC` export $DOC as a sqlite database with all its child requirements and their associated metadata.
- 'mdoors export web' export a static website generated from the requirements, where each document is a single html page.

All of the above cli functionality should be a built on a shared core library that ingests and regularizees the markdown files into
python datastructures that can be worked with very easily to implement the requested functionality.

The html is especially important, so to expand on that:
- each document gets its own page, where the url should match the structure of the input files, just with an .html rather than .md extension.
- the markdown -> html generator should be very simple so that it is easy to customize 
- each document should also have a "tree" view page generated, that shows connections from requirements inside the document to other requirements.
- there should be a requirement search page where all requirements in the project can be searched through, and filtered based on metadata.
  - ideally, the user can also enter arbitrary sql queries against the requirements database.
- as much as possible, use basic html+css+js with no libraries. The site should be very easy to deploy and run locally for development, as simple as using python http.server to host a directory.