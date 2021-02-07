import redis
import json
from django.views.generic.base import RedirectView
from dashboard.forms import NewHubConnectForm
from django.http.response import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse_lazy
from django.views.generic import TemplateView, View

from broker.models import ClientHubDevice, NodeModule

from comms import VALID_CMD
from EagleDaddyCloud.settings import CONFIG

_REDIS_POOL = redis.ConnectionPool(host=CONFIG.proxy.host,
                                   port=int(CONFIG.proxy.port))


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
        with redis.Redis(connection_pool=_REDIS_POOL) as proxy:
            cmd = {str(hub.hub_id): VALID_CMD.DISCOVERY.value}
            proxy.publish(CONFIG.proxy.channel, json.dumps(cmd))
        # # do discovery
        # if hub:
        #     _ = [x.delete() for x in hub.node.all()]
        #     logging.info(f"MANAGER IS CONNECTED: {manager().is_connected()}")
        #     manager().send_hub_command(hub, VALID_CMD.DISCOVERY)

        #     print('discovering new hubs')
        # else:
        #     print('no hub found to send')

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