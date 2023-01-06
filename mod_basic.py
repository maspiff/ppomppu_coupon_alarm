from .setup import *
from .model import ModelItem
import requests
import re
import time
from tool import ToolNotify

site_map = {
    'ppomppu': '뽐뿌',
}
board_map = {
    'coupon': '쿠폰',
}
site_board_map = {
    'ppomppu': ['coupon'],
}

def get_url_prefix(site_name):
    url_prefix = ''
    if site_name == 'ppomppu':
        url_prefix = 'https://www.ppomppu.co.kr/zboard/'
    return url_prefix


class ModuleBasic(PluginModuleBase):
    def __init__(self, P):
        super(ModuleBasic, self).__init__(P, name='basic',
                                          first_menu='setting', scheduler_desc="뽐뿌 쿠폰 알람")
        self.db_default = {
            f'db_version': '1.8',
            f'{self.name}_auto_start': 'False',
            f'{self.name}_interval': '1',
            f'{self.name}_db_delete_day': '7',
            f'{self.name}_db_auto_delete': 'False',
            f'{P.package_name}_item_last_list_option': '',
            f'notify_mode': 'always',
            'use_site_ppomppu': 'False',
            'use_board_ppomppu_coupon': 'False',
            'alarm_message_template': '`{title}`\n{url}\n{mall_url}',
            'selenium_remote_address': ''
        }
        self.web_list_model = ModelItem

    def process_menu(self, sub, req):
        arg = P.ModelSetting.to_dict()
        if sub == 'setting':
            arg['is_include'] = F.scheduler.is_include(
                self.get_scheduler_name())
            arg['is_running'] = F.scheduler.is_running(
                self.get_scheduler_name())
        if sub == 'list':
            arg = self.web_list_model.get_list()
        return render_template(f'{P.package_name}_{self.name}_{sub}.html', arg=arg, site_map=site_map, board_map=board_map, site_board_map=site_board_map)

    def process_command(self, command, arg1, arg2, arg3, req):
        ret = {'ret': 'success'}
        if command == 'test':
            ret['status'] = 'warn'
            ret['title'] = '테스트'
            ret['data'] = '테스트 내용'
        return jsonify(ret)

    def scheduler_function(self):
        self.scrap_items()

    def scrap_detail(self):
        ret = {
            'status': 'success'
        }
        P.logger.info("scrap_details")
        regex = None
        items = ModelItem.get_non_shopping_mall_lsit()
        for item in items:
            mall_url = ''
            if item.site_name == 'ppomppu':
                regex = r'div class=wordfix>링크: \<a .+\>(?P<mall_url>.+)\</a\>'
            if regex:
                sess = requests.session()
                getdata = sess.get(get_url_prefix(item.site_name) + item.url)
                find_result = re.compile(regex).search(getdata.text)
                if find_result:
                    mall_url = find_result.groupdict().get('mall_url', '')
            item.mall_url = mall_url
            ModelItem.save(item)
        return ret

    def scrap_items(self):
        ret = {
            'status': 'success',
            'data': []
        }
        P.logger.info("scrap_items")
        sess = requests.session()
        # get model settings.
        if P.ModelSetting.get('use_site_ppomppu') == 'True':
            boards = site_board_map['ppomppu']
            regex = r'href=\"(?P<url>.+)\"\s+><font class=list_title>(?P<title>.+)<\/font>'
            for board in boards:
                if P.ModelSetting.get(f'use_board_ppomppu_{board}') == 'True':

                    getdata = sess.get(
                        f'https://www.ppomppu.co.kr/zboard/zboard.php?id={board}')
                    matches = re.finditer(regex, getdata.text, re.MULTILINE)
                    for matchNum, match in enumerate(matches, start=1):
                        new_obj = match.groupdict()
                        new_obj['site'] = 'ppomppu'
                        new_obj['board'] = board
                        ret['data'].append(new_obj)

        for row in ret['data']:
            ModelItem.update({
                'site_name': row['site'],
                'board_name': row['board'],
                'title': row['title'],
                'url': row['url']
            })
        self.process_discord_data()
        return ret

    def process_discord_data(self):
        self.scrap_detail()
        items = ModelItem.get_alarm_target_list()
        if items is None or len(items) == 0:
            return
        msg_template = P.ModelSetting.get('alarm_message_template')
        if msg_template is None or len(msg_template) == 0:
            return
        for item in items:
            if P.ModelSetting.get_bool('use_hotdeal_alarm'):
                title = item.title.replace('&gt;', '>').replace('&lt;', '<')
                site = site_map[item.site_name]
                board = board_map[item.board_name]
                url = get_url_prefix(site_name=item.site_name)+item.url
                mall_url = item.mall_url if item.mall_url and len(
                    item.mall_url) > 0 else ''
                is_send = False
                is_dist_send = False

                if P.ModelSetting.get_bool('use_hotdeal_alarm'):
                    is_send = True

                if is_send is True:
                    msg = msg_template
                    msg = msg.replace('{title}', title).replace('{site}', site).replace(
                        '{board}', board).replace('{mall_url}', mall_url).replace('{url}', url)
                    ToolNotify.send_message(
                        msg, message_id=f"bot_{P.package_name}")

            item.alarm_status = True
            ModelItem.save(item)
