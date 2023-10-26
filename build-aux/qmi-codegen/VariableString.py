# -*- Mode: python; tab-width: 4; indent-tabs-mode: nil; c-basic-offset: 4 -*-
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 2 of the License, or (at your option) any
# later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright (C) 2012 Lanedo GmbH
# Copyright (C) 2012-2022 Aleksander Morgado <aleksander@aleksander.es>
# Copyright (c) 2022 Qualcomm Innovation Center, Inc.
#

import string
import utils
from Variable import Variable

"""
Variable type for Strings ('string' format)
"""
class VariableString(Variable):

    def __init__(self, service, dictionary):

        # Call the parent constructor
        Variable.__init__(self, service, dictionary)

        self.private_format = 'gchar *'
        self.public_format = self.private_format
        self.element_type = 'utf8'

        # Public format for the GIR array compat methods in 1.32
        self.private_format_gir = self.private_format
        self.public_format_gir = self.public_format
        self.element_type_gir = self.element_type

        if 'fixed-size' in dictionary:
            self.is_fixed_size = True
            # Fixed-size strings
            self.needs_dispose = False
            self.length_prefix_size = 0
            self.n_size_prefix_bytes = 0
            self.fixed_size = dictionary['fixed-size']
            self.max_size = ''
        else:
            self.is_fixed_size = False
            self.fixed_size = '-1'
            # Variable-length strings in heap
            self.needs_dispose = True
            self.clear_method = 'qmi_helpers_clear_string'
            self.free_method_gir = 'g_free'
            if 'size-prefix-format' in dictionary:
                if dictionary['size-prefix-format'] == 'guint8':
                    self.length_prefix_size = 8
                    self.n_size_prefix_bytes = 1
                elif dictionary['size-prefix-format'] == 'guint16':
                    self.length_prefix_size = 16
                    self.n_size_prefix_bytes = 2
                else:
                    raise ValueError('Invalid size prefix format (%s): not guint8 or guint16' % dictionary['size-prefix-format'])
            # Strings which are given as the full value of a TLV and which don't have
            # a explicit 'size-prefix-format' will NOT have a length prefix
            elif 'type' in dictionary and dictionary['type'] == 'TLV':
                self.length_prefix_size = 0
                self.n_size_prefix_bytes = 0
            else:
                # Default to UINT8
                self.length_prefix_size = 8
                self.n_size_prefix_bytes = 1
            self.max_size = dictionary['max-size'] if 'max-size' in dictionary else ''


    def emit_buffer_read(self, f, line_prefix, tlv_out, error, variable_name):
        translations = { 'lp'            : line_prefix,
                         'tlv_out'       : tlv_out,
                         'variable_name' : variable_name,
                         'error'         : error }

        if self.is_fixed_size:
            translations['fixed_size'] = self.fixed_size

            # Fixed sized strings exposed in public fields will need to be
            # explicitly allocated in heap
            if self.public:
                translations['fixed_size_plus_one'] = int(self.fixed_size) + 1
                template = (
                    '${lp}${variable_name} = g_malloc (${fixed_size_plus_one});\n'
                    '${lp}if (!qmi_message_tlv_read_fixed_size_string (message, init_offset, &offset, ${fixed_size}, &${variable_name}[0], ${error})) {\n'
                    '${lp}    g_free (${variable_name});\n'
                    '${lp}    ${variable_name} = NULL;\n'
                    '${lp}    goto ${tlv_out};\n'
                    '${lp}}\n'
                    '${lp}${variable_name}[${fixed_size}] = \'\\0\';\n')
            else:
                template = (
                    '${lp}if (!qmi_message_tlv_read_fixed_size_string (message, init_offset, &offset, ${fixed_size}, &${variable_name}[0], ${error}))\n'
                    '${lp}    goto ${tlv_out};\n'
                    '${lp}${variable_name}[${fixed_size}] = \'\\0\';\n')
        else:
            translations['n_size_prefix_bytes'] = self.n_size_prefix_bytes
            translations['max_size'] = self.max_size if self.max_size != '' else '0'
            template = (
                '${lp}if (!qmi_message_tlv_read_string (message, init_offset, &offset, ${n_size_prefix_bytes}, ${max_size}, &(${variable_name}), ${error}))\n'
                '${lp}    goto ${tlv_out};\n')
        f.write(string.Template(template).substitute(translations))


    def emit_buffer_write(self, f, line_prefix, tlv_name, variable_name):
        translations = { 'lp'                  : line_prefix,
                         'tlv_name'            : tlv_name,
                         'variable_name'       : variable_name,
                         'fixed_size'          : self.fixed_size,
                         'n_size_prefix_bytes' : self.n_size_prefix_bytes }

        template = (
            '${lp}if (!qmi_message_tlv_write_string (self, ${n_size_prefix_bytes}, ${variable_name}, ${fixed_size}, error)) {\n'
            '${lp}    g_prefix_error (error, "Cannot write string in TLV \'${tlv_name}\': ");\n'
            '${lp}    return NULL;\n'
            '${lp}}\n')

        f.write(string.Template(template).substitute(translations))


    def emit_get_printable(self, f, line_prefix, is_personal):
        translations = { 'lp' : line_prefix }

        if self.is_fixed_size:
            translations['fixed_size'] = self.fixed_size
            translations['fixed_size_plus_one'] = int(self.fixed_size) + 1
            template = (
                '\n'
                '${lp}{\n'
                '${lp}    gchar tmp[${fixed_size_plus_one}] = { \'\\0\' };\n'
                '\n'
                '${lp}    if (!qmi_message_tlv_read_fixed_size_string (message, init_offset, &offset, ${fixed_size}, &tmp[0], &error))\n'
                '${lp}        goto out;\n')
        else:
            translations['n_size_prefix_bytes'] = self.n_size_prefix_bytes
            translations['max_size'] = self.max_size if self.max_size != '' else '0'
            template = (
                '\n'
                '${lp}{\n'
                '${lp}    g_autofree gchar *tmp = NULL;\n'
                '\n'
                '${lp}    if (!qmi_message_tlv_read_string (message, init_offset, &offset, ${n_size_prefix_bytes}, ${max_size}, &tmp, &error))\n'
                '${lp}        goto out;\n')

        if self.personal_info or is_personal:
            translations['if_show_field'] = 'if (qmi_utils_get_show_personal_info ()) '
        else:
            translations['if_show_field'] = ''

        template += (
            '${lp}    ${if_show_field}{\n'
            '${lp}        g_string_append (printable, tmp);\n')

        if self.personal_info or is_personal:
            template += (
                '${lp}    } else {\n'
                '${lp}        g_string_append_printf (printable, "\'###\'");\n')

        template += (
            '${lp}    }\n'
            '${lp}}\n')

        f.write(string.Template(template).substitute(translations))


    def build_variable_declaration(self, line_prefix, variable_name):
        translations = { 'lp'   : line_prefix,
                         'name' : variable_name }

        if self.is_fixed_size:
            translations['fixed_size_plus_one'] = int(self.fixed_size) + 1
            template = (
                '${lp}gchar ${name}[${fixed_size_plus_one}];\n')
        else:
            template = (
                '${lp}gchar *${name};\n')
        return string.Template(template).substitute(translations)


    def build_struct_field_declaration(self, line_prefix, variable_name):
        translations = { 'lp'   : line_prefix,
                         'name' : variable_name }

        # Fixed sized strings given in public structs are given as pointers,
        # instead of as fixed-sized arrays directly in the struct.
        template = (
            '${lp}gchar *${name};\n')
        return string.Template(template).substitute(translations)


    def build_getter_declaration(self, line_prefix, variable_name):
        if not self.visible:
            return ""

        translations = { 'lp'   : line_prefix,
                         'name' : variable_name }

        template = (
            '${lp}const gchar **${name},\n')
        return string.Template(template).substitute(translations)


    def build_getter_documentation(self, line_prefix, variable_name):
        if not self.visible:
            return ""

        translations = { 'lp'   : line_prefix,
                         'name' : variable_name }

        template = (
            '${lp}@${name}: (out)(optional)(transfer none): a placeholder for the output constant string, or %NULL if not required.\n')
        return string.Template(template).substitute(translations)


    def build_getter_implementation(self, line_prefix, variable_name_from, variable_name_to):
        if not self.visible:
            return ""

        translations = { 'lp'   : line_prefix,
                         'from' : variable_name_from,
                         'to'   : variable_name_to }

        template = (
            '${lp}if (${to})\n'
            '${lp}    *${to} = ${from};\n')
        return string.Template(template).substitute(translations)


    def build_setter_declaration(self, line_prefix, variable_name):
        if not self.visible:
            return ""

        translations = { 'lp'   : line_prefix,
                         'name' : variable_name }

        template = (
            '${lp}const gchar *${name},\n')
        return string.Template(template).substitute(translations)


    def build_setter_documentation(self, line_prefix, variable_name):
        if not self.visible:
            return ""

        translations = { 'lp'   : line_prefix,
                         'name' : variable_name }

        if self.is_fixed_size:
            translations['fixed_size'] = self.fixed_size
            template = (
                '${lp}@${name}: a constant string of exactly ${fixed_size} characters.\n')
        elif self.max_size != '':
            translations['max_size'] = self.max_size
            template = (
                '${lp}@${name}: a constant string with a maximum length of ${max_size} characters.\n')
        else:
            template = (
                '${lp}@${name}: a constant string.\n')
        return string.Template(template).substitute(translations)


    def build_setter_implementation(self, line_prefix, variable_name_from, variable_name_to):
        if not self.visible:
            return ""

        translations = { 'lp'   : line_prefix,
                         'from' : variable_name_from,
                         'to'   : variable_name_to }

        if self.is_fixed_size:
            translations['fixed_size'] = self.fixed_size
            template = (
                '${lp}if (!${from} || strlen (${from}) != ${fixed_size}) {\n'
                '${lp}    g_set_error (error,\n'
                '${lp}                 QMI_CORE_ERROR,\n'
                '${lp}                 QMI_CORE_ERROR_INVALID_ARGS,\n'
                '${lp}                 "Input variable \'${from}\' must be ${fixed_size} characters long");\n'
                '${lp}    return FALSE;\n'
                '${lp}}\n'
                '${lp}memcpy (${to}, ${from}, ${fixed_size});\n'
                '${lp}${to}[${fixed_size}] = \'\\0\';\n')
        else:
            template = ''
            if self.max_size != '':
                translations['max_size'] = self.max_size
                template += (
                    '${lp}if (${from} && strlen (${from}) > ${max_size}) {\n'
                    '${lp}    g_set_error (error,\n'
                    '${lp}                 QMI_CORE_ERROR,\n'
                    '${lp}                 QMI_CORE_ERROR_INVALID_ARGS,\n'
                    '${lp}                 "Input variable \'${from}\' must be less than ${max_size} characters long");\n'
                    '${lp}    return FALSE;\n'
                    '${lp}}\n')
            template += (
                '${lp}g_free (${to});\n'
                '${lp}${to} = g_strdup (${from} ? ${from} : "");\n')

        return string.Template(template).substitute(translations)


    def build_struct_field_documentation(self, line_prefix, variable_name):
        translations = { 'lp'   : line_prefix,
                         'name' : variable_name }

        if self.is_fixed_size:
            translations['fixed_size'] = self.fixed_size
            template = (
                '${lp}@${name}: a string of exactly ${fixed_size} characters.\n')
        elif self.max_size != '':
            translations['max_size'] = self.max_size
            template = (
                '${lp}@${name}: a string with a maximum length of ${max_size} characters.\n')
        else:
            template = (
                '${lp}@${name}: a string.\n')
        return string.Template(template).substitute(translations)


    def build_dispose(self, line_prefix, variable_name):
        # Fixed-size strings don't need dispose
        if self.is_fixed_size and not self.public:
            return ''

        translations = { 'lp'            : line_prefix,
                         'variable_name' : variable_name }

        template = (
            '${lp}g_clear_pointer (&${variable_name}, (GDestroyNotify)g_free);\n')
        return string.Template(template).substitute(translations)


    def build_copy_gir(self, line_prefix, variable_name_from, variable_name_to):
        translations = { 'lp'                 : line_prefix,
                         'variable_name_from' : variable_name_from,
                         'variable_name_to'   : variable_name_to }

        template = (
            '${lp}${variable_name_to} = g_strdup (${variable_name_from});\n')
        return string.Template(template).substitute(translations)


    def build_copy_to_gir(self, line_prefix, variable_name_from, variable_name_to):
        return self.build_copy_gir (line_prefix, variable_name_from, variable_name_to)


    def build_copy_from_gir(self, line_prefix, variable_name_from, variable_name_to):
        return self.build_copy_gir (line_prefix, variable_name_from, variable_name_to)


    def flag_public(self):
        # Call the parent method
        Variable.flag_public(self)
        # Fixed-sized strings will need dispose if they are in the public header
        if self.is_fixed_size:
            self.needs_dispose = True
