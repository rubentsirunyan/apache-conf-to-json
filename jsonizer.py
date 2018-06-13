from parse_apache_configs import parse_config
import json
import re
import pickle
import argparse


parser = argparse.ArgumentParser(description='Jsonify Apache configuration.')
parser.add_argument("-i", "--input", dest="input",
                    help="Apache config file path.", nargs='?', required=True)
parser.add_argument("-o", "--output", dest="output",
                    help="Output file.", nargs='?')
parser.add_argument("-s", "--servername", dest="servername",
                    help="The desired servername.", nargs='?')
parser.add_argument("-c", "--from-cache", dest="cache",
                    help="Use cached parsed config.", action="store_true")

arguments = parser.parse_args()

APACHE_CONF_FILE = arguments.input
OUTPUT_FILE = arguments.output
DESIRED_VHOST = arguments.servername
FROM_CACHE = arguments.cache


if FROM_CACHE:
    with open('data.pkl', 'rb') as f:
        apache_config = pickle.load(f)
else:
    with open('data.pkl', 'wb') as f:
        apache_parse_obj = parse_config.ParseApacheConfig(
            apache_config_path=APACHE_CONF_FILE)
        apache_config = apache_parse_obj.parse_config()
        pickle.dump(apache_config, f, pickle.HIGHEST_PROTOCOL)


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
                "To": remove_quotes(tmp_lst[1])
            }
        })


def order_rewrites(directive_name, dict_section, dir_inst, flags):
    tmp_lst = list(
        filter(None, re.split(r'(?:(?<!\\) )', dir_inst.args))
    )
    if str(flags) in tmp_lst[1]:
        tmp_lst[1] = tmp_lst[1].split(flags)[0]
    flags = str(flags)[1:-1].split(',') if len(flags) > 2 else []
    parse_dict[dict_section].append({
        directive_name: {
            "From": remove_quotes(tmp_lst[0]),
            "To": remove_quotes(tmp_lst[1]),
            "Flags": flags
        }
    })


def separate_rewrites(directive_name, dir_inst, parse_dict):
    if directive_name in dir_inst.name:
        flags = re.findall(
            "\[(?:[A-Z]+)(?:=.*)?(?:,(?:[A-Z]+)(?:=.*)?)+?\]", dir_inst.args
        )
        if len(flags) > 0:
            flags = flags[0]
        if 'P' in flags:
            order_rewrites("RewriteRule", "Proxies", dir_inst, flags)
        else:
            order_rewrites("RewriteRule", "Rewrites", dir_inst, flags)


def separate_balancers(tag_inst, parse_dict):
    if 'Proxy' in tag_inst.open_tag:
        tmp_dict = {}
        tmp_dict["Name"] = remove_quotes(tag_inst.open_tag.split(' ')[1][:-1])
        tmp_dict["BalancerMembers"] = []
        for directive in tag_inst:
            if isinstance(directive, parse_config.Directive):
                if 'BalancerMember' in directive.name:
                    tmp_dict['BalancerMembers'].append(
                        remove_quotes(directive.args)
                    )
                    # print({"Name": k.name, "Args": k.args})
        parse_dict['Balancers'].append(tmp_dict)


def sepatare_anything(dir_inst, parse_dict):
    managed_directives = [
        "ServerName",
        "ServerAlias",
        "ProxyPass",
        "ProxyPassReverse",
        "RewriteRule"
    ]

    # if dir_inst.name not in managed_directives:
    #     parse_dict[dir_inst.name] = dir_inst.args

    if dir_inst.name not in managed_directives:
        if "List of {}".format(dir_inst.name) in parse_dict:
            parse_dict["List of {}".format(dir_inst.name)].append(
                {dir_inst.name: dir_inst.args}
            )
        else:
            if dir_inst.name in parse_dict:
                parse_dict["List of {}".format(dir_inst.name)] = []
                parse_dict["List of {}".format(dir_inst.name)].append(
                    {dir_inst.name: parse_dict[dir_inst.name]}
                )
                parse_dict["List of {}".format(dir_inst.name)].append(
                    {dir_inst.name: dir_inst.args}
                )
                del parse_dict[dir_inst.name]
            else:
                parse_dict[dir_inst.name] = dir_inst.args


def build_dict(inst, vhost=True):
    if vhost:
        for j in inst:
            if isinstance(j, parse_config.Directive):
                if DESIRED_VHOST:
                    if j.name == "ServerName" and j.args != DESIRED_VHOST:
                        break
                sepatare_server_names("ServerName", j, parse_dict)
                sepatare_server_aliases("ServerAlias", j, parse_dict)
                separate_proxies("ProxyPass", j, parse_dict)
                separate_proxies("ProxyPassReverse", j, parse_dict)
                separate_rewrites("RewriteRule", j, parse_dict)
                sepatare_anything(j, parse_dict)

            if isinstance(j, parse_config.NestedTags):
                separate_balancers(j, parse_dict)
        else:
            vhost_list.append(parse_dict)
    else:
        if isinstance(inst, parse_config.Directive):
            sepatare_server_names("ServerName", inst, parse_dict_no_vhost)
            sepatare_server_aliases("ServerAlias", inst, parse_dict_no_vhost)
            separate_proxies("ProxyPass", inst, parse_dict_no_vhost)
            separate_proxies("ProxyPassReverse", inst, parse_dict_no_vhost)
            separate_rewrites("RewriteRule", inst, parse_dict_no_vhost)
            sepatare_anything(inst, parse_dict)

        if isinstance(inst, parse_config.NestedTags):
            separate_balancers(inst, parse_dict_no_vhost)


vhost_list = []
parse_dict_no_vhost = {
    "Balancers": [],
    "Server Aliases": [],
    "Proxies": [],
    "Rewrites": []
}

for i in apache_config:
    parse_dict = {
        "Balancers": [],
        "Server Aliases": [],
        "Proxies": [],
        "Rewrites": []
    }
    try:
        if i.close_tag == '</VirtualHost>':
            build_dict(i)
        else:
            build_dict(i, vhost=False)
    except AttributeError as e:
        build_dict(i, vhost=False)

vhost_list.append(parse_dict_no_vhost)

with open(OUTPUT_FILE, 'w') as f:
    json.dump(vhost_list, f, ensure_ascii=False)

# print(json.dumps(vhost_list))
