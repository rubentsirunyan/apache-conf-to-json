from parse_apache_configs import parse_config
import json
import re
import sys


APACHE_CONF_FILE = sys.argv[1]
OUTPUT_FILE = sys.argv[2]

apache_parse_obj = parse_config.ParseApacheConfig(
    apache_config_path=APACHE_CONF_FILE)
apache_config = apache_parse_obj.parse_config()


def remove_quotes(_str):
    if _str.startswith('"'):
        _str = _str[1:]
    if _str.endswith('"'):
        _str = _str[:-1]
    return _str


def sepatare_server_names(directive_name, dir_inst, parse_dict):
    if directive_name in dir_inst.name:
        parse_dict[directive_name] = dir_inst.args


def sepatare_server_aliases(directive_name, dir_inst, parse_dict):
    if directive_name in dir_inst.name:
        parse_dict["Server Aliases"].append(dir_inst.args)


def separate_proxies(directive_name, dir_inst, parse_dict):
    if directive_name in dir_inst.name:
        tmp_lst = list(
            filter(None, re.split(r'(?:(?<!\\) )', dir_inst.args))
        )
        parse_dict['Proxies'].append({
            directive_name: {
                "From": remove_quotes(tmp_lst[0]),
                "To": tmp_lst[1]
            }
        })


def order_rewrites(directive_name, dict_section, dir_inst):
    tmp_lst = list(
        filter(None, re.split(r'(?:(?<!\\) )', dir_inst.args))
    )
    parse_dict[dict_section].append({
        directive_name: {
            "From": remove_quotes(tmp_lst[0]),
            "To": tmp_lst[1],
            "Flags": tmp_lst[2] if len(tmp_lst) > 2 else []
        }
    })


def separate_rewrites(directive_name, dir_inst, parse_dict):
    if directive_name in dir_inst.name:
        flags = re.findall(
            "\[([A-Z]+)(?:=.*)?(?:,([A-Z]+)(?:=.*)?)+?\]", dir_inst.args)
        if len(flags) > 0:
            flags = flags[0]
        if 'P' in flags:
            order_rewrites("RewriteRule", "Proxies", dir_inst)
        # else:
        #     order_rewrites("RewriteRule", "Rewrites", dir_inst)


def separate_balancers(tag_inst, parse_dict):
    if 'Proxy' in tag_inst.open_tag:
        tmp_dict = {}
        tmp_dict["Name"] = remove_quotes(tag_inst.open_tag.split(' ')[1][:-1])
        tmp_dict["BalancerMembers"] = []
        for directive in tag_inst:
            if isinstance(directive, parse_config.Directive):
                if 'BalancerMember' in directive.name:
                    tmp_dict['BalancerMembers'].append(directive.args)
                    # print({"Name": k.name, "Args": k.args})
        parse_dict['Balancers'].append(tmp_dict)


vhost_list = []
for i in apache_config:
    try:
        if i.close_tag == '</VirtualHost>':
            parse_dict = {}
            # print({"Open": i.open_tag, "Close": i.close_tag})
            parse_dict['Balancers'] = []
            parse_dict['Server Aliases'] = []
            parse_dict['Proxies'] = []
            parse_dict['Rewrites'] = []
            for j in i:
                if isinstance(j, parse_config.Directive):
                    sepatare_server_names("ServerName", j, parse_dict)
                    sepatare_server_aliases("ServerAlias", j, parse_dict)
                    separate_proxies("ProxyPass", j, parse_dict)
                    separate_proxies("ProxyPassReverse", j, parse_dict)
                    separate_rewrites("RewriteRule", j, parse_dict)

                if isinstance(j, parse_config.NestedTags):
                    separate_balancers(j, parse_dict)

            vhost_list.append(parse_dict)

    except AttributeError:
        continue

with open(OUTPUT_FILE, 'w') as f:
    json.dump(vhost_list, f, ensure_ascii=False)

# print(json.dumps(vhost_list))
