
import argparse
from datetime import datetime, timedelta
import json
import logging

from bson import ObjectId
from motor import motor_tornado
from tornado import escape, gen, ioloop, web

logging.basicConfig(level=logging.DEBUG)

class _JSONEncoder(json.JSONEncoder):
    """Custom JSON encoder."""

    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        return json.JSONEncoder.default(self, obj)


class CRUD(web.RequestHandler):
    """Base CRUD API Interface"""

    def initialize(self):
        """Connect to document store"""

        self.db = self.settings["db"]
        self.collection = self.db[self.__class__.__name__]
        self.index_args = self.settings.get("index_args", list())

    def write_json(self, document):
        """Format output as JSON"""

        self.set_header("Content-Type", "application/json; charset=UTF-8")
        self.write(escape.utf8(json.dumps(document, cls=_JSONEncoder)))

    def write_dict(self, *args, **kwargs):
        """Format dictionary or parameter list as JSON dictionary"""

        if args:
            if len(args) == 1 and type(args[0]) is dict:
                self.write_json(args[0])
            else:
                raise ValueError
        else:
            self.write_json(kwargs)

    def write_error(self, status_code, **kwargs):
        """Format error as JSON dictionary"""

        if self.settings.get("serve_traceback") and "exc_info" in kwargs:
            self.set_header('Content-Type', 'text/plain')
            for line in traceback.format_exception(*kwargs["exc_info"]):
                self.write(line)
        else:
            self.write_dict(status_code=status_code, reason=self._reason)
        self.finish()

    def decode_and_validate_document(self):
        """Extract and validate documents for insert/update

        Decodes document from JSON request body.  Validation here is applied
        before insertion to MongoDB.  Newer MongoDB versions support schema
        validation but a hook is included to cover anything on top of that.
        """

        document = escape.json_decode(self.request.body)
        self.validate_document(document)
        return document

    def validate_document(self, document):
        """Validate document before insertion

        Raise web.HTTPError(400) if there is a validation error."""

        pass

    @gen.coroutine
    def create_indices(self):
        """Create indices

        This runs during the first POST operation."""

        for (args, kwargs) in self.index_args:
            yield self.collection.create_index(*args, **kwargs)

    @gen.coroutine
    def post(self, document_id):
        """Store new document"""

        # API determines document ID, not client.

        if document_id:
            raise web.HTTPError(400)

        # Decode, validate, and insert document.

        document = self.decode_and_validate_document()
        result = yield self.collection.insert_one(dict(document=document))

        # Create any indices.

        yield self.create_indices()

        # Return inserted document ID for client future reference.

        self.write_dict(document_id=result.inserted_id)

    @gen.coroutine
    def get(self, document_id):
        """Retrieve stored documents"""

        if document_id:
            yield self.get_one_document(document_id)
        else:
            yield self.get_many_documents()

    @gen.coroutine
    def get_one_document(self, document_id):
        """Retrieve one document"""

        result = yield self.collection.find_one({"_id": ObjectId(document_id)})
        if result:
            self.write_dict(result["document"])
        else:
            raise web.HTTPError(404)

    @gen.coroutine
    def get_many_documents(self):
        """Retrieve a list of documents"""

        cursor = self.collection.find()
        documents = dict()
        while (yield cursor.fetch_next):
            result = cursor.next_object()
            documents[str(result["_id"])] = result["document"]
        self.write_dict(documents)

    @gen.coroutine
    def put(self, document_id):
        """Replace existing document"""

        # Document ID is required.

        if not document_id:
            raise web.HTTPError(400)

        # Decode, validate, and replace document.

        document = self.decode_and_validate_document()
        result = yield self.collection.find_one_and_update(
                {"_id": ObjectId(document_id)}, 
                {"$set": dict(document=document)})

        # Return empty document.

        self.write_dict()

    @gen.coroutine
    def delete(self, document_id):
        """Delete document"""

        # Find document by ID and remove it.

        result = yield self.collection.delete_one({"_id": ObjectId(document_id)})

        # Return empty document if it succeeded.

        if result.deleted_count == 1:
            self.write_dict()
        else:
            raise web.HTTPError(400)


def create_application(cls, api_prefix, mongodb_uri, debug):
    class_name = cls.__name__
    db = motor_tornado.MotorClient(mongodb_uri)
    db.drop_database(class_name)
    db = motor_tornado.MotorClient(mongodb_uri)[class_name]
    settings = dict(debug=debug, db=db)
    return web.Application([
        (r"{}(\w*)".format(api_prefix), cls),
    ], **settings)


if __name__ == "__main__":

    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--debug", "-d", help="Return traceback on error", action="store_true")
    parser.add_argument("--mongodb-uri", "-m", help="MongoDB URI", default="mongodb://db:27017")
    parser.add_argument("--port", "-p", help="Listen on this port", default=8888, type=int)
    parser.add_argument("--api-prefix", "-a", help="API prefix", default="/")
    args = parser.parse_args()

    application = create_application(CRUD, args.api_prefix, args.mongodb_uri, args.debug)
    application.listen(args.port)
    ioloop.IOLoop.current().start()
