import json

try:
    import pydgraph
    enabled = True
except ImportError:
    enabled = False

from redash.query_runner import BaseQueryRunner, register
from redash.utils import json_dumps, json_loads


class Dgraph(BaseQueryRunner):
    noop_query = """
    {
      test() {
      }
    }
    """

    @classmethod
    def configuration_schema(cls):
        return {
            "type": "object",
            "properties": {
                "user": {
                    "type": "string"
                },
                "password": {
                    "type": "string"
                },
                "servers": {
                    "type": "string"
                }
            },
            "order": ["servers", "user", "password"],
            "required": ["servers"],
            "secret": ["password"]
        }

    @classmethod
    def type(cls):
        return "dgraph"

    @classmethod
    def enabled(cls):
        return enabled

    @classmethod
    def annotate_query(cls):
        """Dgraph uses '#' as a comment delimiter, not '/* */'"""
        return False

    def run_dgraph_query_raw(self, query):

        servers = self.configuration.get('servers')

        client_stub = pydgraph.DgraphClientStub(servers)
        client = pydgraph.DgraphClient(client_stub)

        txn = client.txn(read_only=True)
        try:
            response_raw = txn.query(query)

            data = json.loads(response_raw.json)

            return data

        except Exception as e:
            raise e
        finally:
            txn.discard()
            client_stub.close()

    def run_query(self, query, user):

        json_data = None
        error = None

        try:
            data = self.run_dgraph_query_raw(query)

            first_key = next(iter(data.keys()))
            first_node = data[first_key]

            # grab all the column names
            column_names = set().union(*first_node)
            # create a dict for column names in the format that the API wants
            # the type as 'string' is just a hack for now
            columns = [{'name': c, 'friendly_name': c, 'type': 'string'} for c in column_names]
            # finally, assemble both the columns and data
            data = {'columns': columns, 'rows': first_node}

            json_data = json_dumps(data)

        except Exception as e:
            error = e

        return json_data, error

    def get_schema(self, get_stats=False):
        """Queries Dgraph for all the predicates, their types, their tokenizers, etc.

        Dgraph only has one schema, and there's no such things as columns"""
        query = "schema {}"

        results = self.run_dgraph_query_raw(query)

        schema = {}

        for row in results['schema']:
            table_name = row['predicate']

            if table_name not in schema:
                schema[table_name] = {'name': table_name, 'columns': []}

        return schema.values()


register(Dgraph)
