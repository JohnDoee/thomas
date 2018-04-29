# from six.moves.urllib.parse import urlsplit

from twisted.web import resource


# class HttpApi(resource.Resource):
#     isLeaf = True

#     def render_GET(self, request):
#         url = request.args.get('url')
#         if not url:
#             return resource.NoResource()
#         url = url[0]
#         parsed_url = urlsplit(url)

#         plugin_cls = InputBase.find_plugin(parsed_url.scheme)
#         plugin = plugin_cls(url, **ROOT_RESOURCE.plugin_configs.get('input.%s' % plugin_cls.plugin_name, {}))


ROOT_RESOURCE = resource.Resource()
# ROOT_RESOURCE.plugin_configs = {}
# ROOT_RESOURCE.putChild('api', HttpApi())
