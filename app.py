
from datetime import datetime, timedelta
import logging
logging.basicConfig(level=logging.DEBUG)
import os

import json

from bson import ObjectId
import motor.motor_tornado
from tornado import gen, escape, ioloop, web

DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S"

class _JSONEncoder(json.JSONEncoder):

    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        elif isinstance(obj, datetime):
            return obj.strftime(DATETIME_FORMAT)
        return json.JSONEncoder.default(self, obj)


class API(web.RequestHandler):

    def initialize(self):
        self.db = self.settings["db"]
        self.collection = self.db[self.__class__.__name__]

    def write_json(self, document):
        self.set_header("Content-Type", "application/json; charset=UTF-8")
        self.write(escape.utf8(json.dumps(document, cls=_JSONEncoder)))

    def write_dict(self, *args, **kwargs):
        if args:
            if len(args) == 1 and type(args[0]) is dict:
                self.write_json(args[0])
            else:
                raise ValueError
        else:
            self.write_json(kwargs)

    def write_error(self, status_code, **kwargs):
        if self.settings.get("serve_traceback") and "exc_info" in kwargs:
            self.set_header('Content-Type', 'text/plain')
            for line in traceback.format_exception(*kwargs["exc_info"]):
                self.write(line)
        else:
            self.write_dict(status_code=status_code, reason=self._reason)
        self.finish()


class APIv1(API):

    @gen.coroutine
    def post(self, document_id):
        """Store document"""

        # API determines document ID, not client.

        if document_id:
            raise web.HTTPError(400)

        # Decode document from JSON request body.

        document = escape.json_decode(self.request.body)

        # Documents must have expiration date.  Replace properly formatted 
        # expiration date with datetime version for MongoDB.

        try:
            expires = datetime.strptime(document["expires"], DATETIME_FORMAT)
            document["expires"] = expires
        except:
            raise web.HTTPError(400)

        # Insert document.

        result = yield self.collection.insert_one(dict(document=document))
        yield self.collection.create_index("document.expires", expireAfterSeconds=0)

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

        # Decode document from JSON request body.

        document = escape.json_decode(self.request.body)

        # Documents must have expiration date.  Replace properly formatted 
        # expiration date with datetime version for MongoDB.

        try:
            expires = datetime.strptime(document["expires"], DATETIME_FORMAT)
            document["expires"] = expires
        except:
            raise web.HTTPError(400)

        # Replace document.

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


def create_application(cls, prefix):
    db = motor.motor_tornado.MotorClient("mongodb://db:27017")
    db.drop_database(cls.__name__)
    db = motor.motor_tornado.MotorClient("mongodb://db:27017")[cls.__name__]
    settings = dict(debug=True, serve_traceback=False, db=db)
    return web.Application([
        (r"{}api/v1/documents/(\w*)".format(prefix), cls),
    ], **settings)


if __name__ == "__main__":
    prefix = os.environ.get("JUPYTERHUB_SERVICE_PREFIX", "/")
    application = create_application(APIv1, prefix)
    application.listen(8888)
    ioloop.IOLoop.current().start()

