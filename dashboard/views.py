import redis
import logging
from django.views.generic.base import RedirectView
from dashboard.forms import NewHubConnectForm
from django.http.response import HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.urls import reverse_lazy, reverse
from django.views.generic import TemplateView, View

from broker.models import ClientHubDevice, NodeModule

from edcomms import EDCommand
from EagleDaddyCloud.settings import CONFIG
from broker.utils import send_proxy_data

_REDIS_POOL = redis.ConnectionPool(host=CONFIG.proxy.host,
                                   port=int(CONFIG.proxy.port),
                                   health_check_interval=15)


def check_for_nodes(request):
    """
    check for nodes and return
    """
    nodes = NodeModule.objects.all()

    node_j = {'nodes': list()}
    for node in nodes:
        url_path = reverse('node_remove', args=[str(node.address)])
        logging.error(url_path)
        node_j['nodes'].append({
            'address64': node.address,
            'node_id': node.node_id,
            'url': str(url_path)
        })
    return JsonResponse(node_j)


def discover_nodes(request):
    """
    Do the actual discovering of nodes
    """
    hub_id = request.GET.get('hub_id')
    if not hub_id:
        return JsonResponse({'response': "hub_id not found in request"})

    hub = ClientHubDevice.objects.filter(hub_id=hub_id).first()

    # with redis.Redis(connection_pool=_REDIS_POOL) as proxy:
    cmd = {str(hub.hub_id): EDCommand.discovery.value}
    #     proxy.publish(CONFIG.proxy.channel, json.dumps(cmd))
    success = send_proxy_data(_REDIS_POOL, cmd)
    if not success:
        err_msg = "Unable to send data to proxy server."
        logging.error(err_msg)
        return JsonResponse({'response': err_msg})

    return JsonResponse({'response': str(success)})


class TestView(View):
    def get(self, request):
        return render(request, "hubs.html", {})


class HubMainView(TemplateView):
    template_name = "hubs.html"

    def get_user_linked_hubs(self, user):
        user_account = getattr(user, 'account', None)
        hubs = list(
            ClientHubDevice.objects.filter(
                account=user_account).all()) if user_account else []

        return hubs

    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        context['hubs'] = self.get_user_linked_hubs(request.user)
        context['new_hub_form'] = NewHubConnectForm()
        return self.render_to_response(context)

    def post(self, request, *args, **kwargs):
        connect_passphrase = request.POST['connect_passphrase']
        if connect_passphrase:
            hub = ClientHubDevice.objects.filter(
                connect_passphrase=connect_passphrase).first()
            print(hub)
            if hub:
                account = request.user.account
                hub.account = account
                hub.save()
        return HttpResponseRedirect(reverse_lazy('hub_main_view'))


class RemoveNode(RedirectView):
    pattern_name = "hub_main_view"

    def get(self, request, node_id, *args, **kwargs):
        node = NodeModule.objects.filter(address=node_id).first()
        if not node:
            return
        node.delete()
        return super().get(request, *args, **kwargs)


class DiscoverNewNodes(RedirectView):
    pattern_name = "hub_main_view"

    def do_discovery(self, hub_id):
        hub = ClientHubDevice.objects.filter(hub_id=hub_id).first()

        # with redis.Redis(connection_pool=_REDIS_POOL) as proxy:
        cmd = {str(hub.hub_id): EDCommand.discovery.value}
        #     proxy.publish(CONFIG.proxy.channel, json.dumps(cmd))
        success = send_proxy_data(_REDIS_POOL, cmd)
        if not success:
            logging.error("Unable to send data to proxy server.")
            return

    def get(self, request, hub_id, *args, **kwargs):
        self.do_discovery(hub_id)
        return super().get(request, *args, **kwargs)


class HubInfoView(TemplateView):
    template_name = "dashboard_base.html"

    def get_user_hubs(self, request):
        account = getattr(request.user, 'account', None)
        hubs = list(ClientHubDevice.objects.filter(
            account=account).all()) if account else []
        return hubs

    def get(self, request):
        context = dict()

        all_hubs = self.get_user_hubs(request)
        context['hubs'] = all_hubs

        return self.render_to_response(context)


class NodeInfoView(HubInfoView):
    template_name = "hub_info.html"

    def get(self, request, hub_name, node_address):
        hubs = self.get_user_hubs(request)
        node = NodeModule.objects.filter(
            address=node_address).first()  # will be unique
        selected_hub = node.hub

        context = {
            'hubs': hubs,
            'selected_node': node,
            'selected_hub': selected_hub
        }
        return render(request, self.template_name, context)