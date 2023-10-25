# -*- Mode: python; tab-width: 4; indent-tabs-mode: nil -*-
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
import VariableFactory
import TypeFactory

"""
The Field class takes care of handling Input and Output TLVs
"""
class Field:

    """
    Constructor
    """
    def __init__(self, service, prefix, dictionary, common_objects_dictionary, container_type, static):
        # The current QMI service
        self.service = service
        # The field prefix, usually the name of the Container,
        #  e.g. "Qmi Message Ctl Something Output"
        self.prefix = prefix
        # The name of the specific field, e.g. "Result"
        self.name = dictionary['name']
        # The specific TLV ID
        self.id = dictionary['id']
        # Overridden mandatory field, the default is calculated from id
        self._mandatory = dictionary.get('mandatory')
        # The type, which must always be "TLV"
        self.type = dictionary['type']
        # The container type, which must be either "Input" or "Output"
        self.container_type = container_type
        # Whether the whole field is internally used only
        self.static = static

        # Create the composed full name (prefix + name),
        #  e.g. "Qmi Message Ctl Something Output Result"
        self.fullname = dictionary['fullname'] if 'fullname' in dictionary else self.prefix + ' ' + self.name

        # libqmi version where the message was introduced
        self.since = dictionary['since'] if 'since' in dictionary else None
        if self.since is None:
            raise ValueError('TLV ' + self.fullname + ' requires a "since" tag specifying the major version where it was introduced')

        # TLVs can no longer be structs, they must be sequences instead
        if dictionary['format'] == 'struct':
            raise ValueError('TLV ' + self.fullname + ' cannot have type "struct": use "sequence" instead')

        # Create our variable object
        self.variable = VariableFactory.create_variable(self.service, dictionary, self.fullname, self.container_type)

        # Create the variable name within the Container
        self.variable_name = 'arg_' + utils.build_underscore_name(self.name).lower()

        # Create the ID enumeration name
        self.id_enum_name = utils.build_underscore_name(self.prefix + ' TLV ' + self.name).upper()

        # Output Fields may have prerequisites
        self.prerequisites = []
        if 'prerequisites' in dictionary:
            self.prerequisites = dictionary['prerequisites']
            # First, look for references to common types
            for prerequisite_dictionary in self.prerequisites:
                if 'common-ref' in prerequisite_dictionary:
                    for common in common_objects_dictionary:
                        if common['type'] == 'prerequisite' and \
                           common['common-ref'] == prerequisite_dictionary['common-ref']:
                           # Replace the reference with a copy of the common dictionary
                           copy = dict(common)
                           self.prerequisites.remove(prerequisite_dictionary)
                           self.prerequisites.append(copy)
                           break
                    else:
                        raise RuntimeError('Common type \'%s\' not found' % prerequisite_dictionary['name'])

        if 'personal-info' in dictionary:
            self.personal_info = True;
        else:
            self.personal_info = False;


    @property
    def mandatory(self):
        if self._mandatory is None:
            return int(self.id, 0) < 0x10
        return self._mandatory == 'yes'


    """
    Emit new types required by this field
    """
    def emit_types(self, hfile, cfile):
        if not TypeFactory.is_type_emitted(self.fullname):
            TypeFactory.set_type_emitted(self.fullname)
            self.variable.emit_types(hfile, cfile, self.since, False)
            if self.variable.needs_compat_gir and self.service != 'CTL':
                self.variable.emit_types_gir(hfile, cfile, self.since)


    """
    Common getter logic
    """
    def emit_getter_common(self, hfile, cfile, dec, doc, imp, since, suffix_gir):
        translations = { 'name'                : self.name,
                         'variable_name'       : self.variable_name,
                         'variable_getter_dec' : dec,
                         'variable_getter_doc' : doc,
                         'variable_getter_imp' : imp,
                         'underscore'          : utils.build_underscore_name(self.name),
                         'suffix_gir'          : suffix_gir,
                         'prefix_camelcase'    : utils.build_camelcase_name(self.prefix),
                         'prefix_underscore'   : utils.build_underscore_name(self.prefix),
                         'since'               : since,
                         'static'              : 'static ' if self.static else '' }

        # Emit the getter header
        template = '\n'
        if not self.static and self.service != 'CTL':
            template += (
                '\n'
                '/**\n')

            if self.variable.needs_compat_gir:
                # Rename the GIR specific method to the original method name, and
                # skip the original method completely
                if suffix_gir == '':
                    template += (
                        ' * ${prefix_underscore}_get_${underscore}: (skip)\n')
                else:
                    template += (
                        ' * ${prefix_underscore}_get_${underscore}${suffix_gir}: (rename-to ${prefix_underscore}_get_${underscore})\n')
            else:
                if suffix_gir != '':
                    raise RuntimeError('GIR suffix given and variable does not need compat GIR support')
                template += (
                    ' * ${prefix_underscore}_get_${underscore}:\n')

            template += (
                ' * @self: a #${prefix_camelcase}.\n'
                '${variable_getter_doc}'
                ' * @error: Return location for error or %NULL.\n'
                ' *\n'
                ' * Get the \'${name}\' field from @self.\n')

            if self.variable.needs_compat_gir:
                if suffix_gir != '':
                    template += (
                        ' *\n'
                        ' * Version of ${prefix_underscore}_get_${underscore}() using arrays of pointers to\n'
                        ' * structs instead of arrays of structs, for easier binding in other languages.\n')

            template += (
                ' *\n'
                ' * Returns: (skip): %TRUE if the field is found, %FALSE otherwise.\n'
                ' *\n'
                ' * Since: ${since}\n'
                ' */\n')
        template += (
            '${static}gboolean ${prefix_underscore}_get_${underscore}${suffix_gir} (\n'
            '    ${prefix_camelcase} *self,\n'
            '${variable_getter_dec}'
            '    GError **error);\n')
        hfile.write(string.Template(template).substitute(translations))

        # Emit the getter source
        template = (
            '\n'
            '${static}gboolean\n'
            '${prefix_underscore}_get_${underscore}${suffix_gir} (\n'
            '    ${prefix_camelcase} *self,\n'
            '${variable_getter_dec}'
            '    GError **error)\n'
            '{\n'
            '    g_return_val_if_fail (self != NULL, FALSE);\n'
            '\n'
            '    if (!self->${variable_name}_set) {\n'
            '        g_set_error (error,\n'
            '                     QMI_CORE_ERROR,\n'
            '                     QMI_CORE_ERROR_TLV_NOT_FOUND,\n'
            '                     "Field \'${name}\' was not found in the message");\n'
            '        return FALSE;\n'
            '    }\n'
            '\n'
            '${variable_getter_imp}'
            '\n'
            '    return TRUE;\n'
            '}\n')
        cfile.write(string.Template(template).substitute(translations))


    """
    Emit the method responsible for declaring variable(s) for this TLV in the
    input/output container
    """
    def emit_variable_declaration(self, cfile):

        template = self.variable.build_variable_declaration('    ', self.variable_name)
        cfile.write(template)

        if self.variable.needs_compat_gir and self.service != 'CTL':
            template = self.variable.build_variable_declaration_gir('    ', self.variable_name)
            cfile.write(template)


    """
    Emit the method responsible for getting this TLV from the input/output
    container
    """
    def emit_getter(self, hfile, cfile):
        input_variable_name = 'value_' + utils.build_underscore_name(self.name)
        dec = self.variable.build_getter_declaration('    ', input_variable_name)
        doc = self.variable.build_getter_documentation(' * ', input_variable_name)
        imp = self.variable.build_getter_implementation('    ', 'self->' + self.variable_name, input_variable_name)
        since = self.since
        self.emit_getter_common(hfile, cfile, dec, doc, imp, since, '')

        if self.variable.needs_compat_gir and self.service != 'CTL':
            input_variable_name = 'value_' + utils.build_underscore_name(self.name)
            dec = self.variable.build_getter_declaration_gir('    ', input_variable_name)
            doc = self.variable.build_getter_documentation_gir(' * ', input_variable_name)
            imp = self.variable.build_getter_implementation_gir('    ', 'self->' + self.variable_name, input_variable_name)
            since = self.since if utils.version_compare('1.32',self.since) > 0 else '1.32'
            self.emit_getter_common(hfile, cfile, dec, doc, imp, since, '_gir')


    """
    Common setter logic
    """
    def emit_setter_common(self, hfile, cfile, dec, doc, imp, since, suffix_gir):
        translations = { 'name'                : self.name,
                         'variable_name'       : self.variable_name,
                         'variable_setter_dec' : dec,
                         'variable_setter_doc' : doc,
                         'variable_setter_imp' : imp,
                         'underscore'          : utils.build_underscore_name(self.name),
                         'prefix_camelcase'    : utils.build_camelcase_name(self.prefix),
                         'prefix_underscore'   : utils.build_underscore_name(self.prefix),
                         'since'               : since,
                         'suffix_gir'          : suffix_gir,
                         'static'              : 'static ' if self.static else '' }

        # Emit the setter header
        template = '\n'
        if not self.static and self.service != 'CTL':
            template += (
                '\n'
                '/**\n')

            if self.variable.needs_compat_gir:
                # Rename the GIR specific method to the original method name, and
                # skip the original method completely
                if suffix_gir == '':
                    template += (
                        ' * ${prefix_underscore}_set_${underscore}: (skip)\n')
                else:
                    template += (
                        ' * ${prefix_underscore}_set_${underscore}${suffix_gir}: (rename-to ${prefix_underscore}_set_${underscore})\n')
            else:
                if suffix_gir != '':
                    raise RuntimeError('GIR suffix given and variable does not need compat GIR support')
                template += (
                    ' * ${prefix_underscore}_set_${underscore}:\n')

            template += (
                ' * @self: a #${prefix_camelcase}.\n'
                '${variable_setter_doc}'
                ' * @error: Return location for error or %NULL.\n'
                ' *\n'
                ' * Set the \'${name}\' field in the message.\n'
                ' *\n'
                ' * Returns: (skip): %TRUE if @value was successfully set, %FALSE otherwise.\n'
                ' *\n'
                ' * Since: ${since}\n'
                ' */\n')
        template += (
            '${static}gboolean ${prefix_underscore}_set_${underscore}${suffix_gir} (\n'
            '    ${prefix_camelcase} *self,\n'
            '${variable_setter_dec}'
            '    GError **error);\n')
        hfile.write(string.Template(template).substitute(translations))

        # Emit the setter source
        template = (
            '\n'
            '${static}gboolean\n'
            '${prefix_underscore}_set_${underscore}${suffix_gir} (\n'
            '    ${prefix_camelcase} *self,\n'
            '${variable_setter_dec}'
            '    GError **error)\n'
            '{\n'
            '    g_return_val_if_fail (self != NULL, FALSE);\n'
            '\n'
            '${variable_setter_imp}'
            '    self->${variable_name}_set = TRUE;\n'
            '\n'
            '    return TRUE;\n'
            '}\n')
        cfile.write(string.Template(template).substitute(translations))

    """
    Emit the method responsible for setting this TLV in the input/output
    container
    """
    def emit_setter(self, hfile, cfile):
        input_variable_name = 'value_' + utils.build_underscore_name(self.name)
        dec = self.variable.build_setter_declaration('    ', input_variable_name)
        doc = self.variable.build_setter_documentation(' * ', input_variable_name)
        imp = self.variable.build_setter_implementation('    ', input_variable_name, 'self->' + self.variable_name)
        since = self.since
        self.emit_setter_common(hfile, cfile, dec, doc, imp, since, '')

        if self.variable.needs_compat_gir and self.service != 'CTL':
            input_variable_name = 'value_' + utils.build_underscore_name(self.name)
            dec = self.variable.build_setter_declaration_gir('    ', input_variable_name)
            doc = self.variable.build_setter_documentation_gir(' * ', input_variable_name)
            imp = self.variable.build_setter_implementation_gir('    ', input_variable_name, 'self->' + self.variable_name)
            since = self.since if utils.version_compare('1.32',self.since) > 0 else '1.32'
            self.emit_setter_common(hfile, cfile, dec, doc, imp, since, '_gir')


    """
    Emit the code responsible for adding the TLV to the QMI message
    """
    def emit_input_tlv_add(self, f, line_prefix):
        translations = { 'name'          : self.name,
                         'tlv_id'        : self.id_enum_name,
                         'variable_name' : self.variable_name,
                         'lp'            : line_prefix }

        template = (
            '${lp}gsize tlv_offset;\n'
            '\n'
            '${lp}if (!(tlv_offset = qmi_message_tlv_write_init (self, (guint8)${tlv_id}, error))) {\n'
            '${lp}    g_prefix_error (error, "Cannot initialize TLV \'${name}\': ");\n'
            '${lp}    return NULL;\n'
            '${lp}}\n'
            '\n')
        f.write(string.Template(template).substitute(translations))

        # Now, write the contents of the variable into the buffer
        self.variable.emit_buffer_write(f, line_prefix, self.name, 'input->' + self.variable_name)

        template = (
            '\n'
            '${lp}if (!qmi_message_tlv_write_complete (self, tlv_offset, error)) {\n'
            '${lp}    g_prefix_error (error, "Cannot complete TLV \'${name}\': ");\n'
            '${lp}    return NULL;\n'
            '${lp}}\n')
        f.write(string.Template(template).substitute(translations))


    """
    Emit the code responsible for checking prerequisites in output TLVs
    """
    def emit_output_prerequisite_check(self, f, line_prefix):
        if self.prerequisites == []:
            f.write('%s/* No Prerequisites for field */\n' % line_prefix)
            return

        for prerequisite in self.prerequisites:
            translations = { 'lp'                     : line_prefix,
                             'prerequisite_field'     : utils.build_underscore_name(prerequisite['field']),
                             'prerequisite_operation' : prerequisite['operation'],
                             'prerequisite_value'     : prerequisite['value'] }
            template = (
                '${lp}/* Prerequisite.... */\n'
                '${lp}if (!(self->arg_${prerequisite_field} ${prerequisite_operation} ${prerequisite_value}))\n'
                '${lp}    break;\n')
            f.write(string.Template(template).substitute(translations))


    """
    Emit the code responsible for retrieving the TLV from the QMI message
    """
    def emit_output_tlv_get(self, f, line_prefix):
        tlv_out = utils.build_underscore_name (self.fullname) + '_out'
        error = 'error' if self.mandatory else 'NULL'
        translations = { 'name'                 : self.name,
                         'container_underscore' : utils.build_underscore_name (self.prefix),
                         'tlv_out'              : tlv_out,
                         'tlv_id'               : self.id_enum_name,
                         'variable_name'        : self.variable_name,
                         'lp'                   : line_prefix,
                         'error'                : error }

        template = (
            '${lp}gsize offset = 0;\n'
            '${lp}gsize init_offset;\n'
            '\n'
            '${lp}if ((init_offset = qmi_message_tlv_read_init (message, ${tlv_id}, NULL, ${error})) == 0) {\n')

        if self.mandatory:
            template += (
                '${lp}    g_prefix_error (${error}, "Couldn\'t get the mandatory ${name} TLV: ");\n'
                '${lp}    ${container_underscore}_unref (self);\n'
                '${lp}    return NULL;\n')
        else:
            template += (
                '${lp}    goto ${tlv_out};\n')

        template += (
            '${lp}}\n')

        f.write(string.Template(template).substitute(translations))

        # Now, read the contents of the buffer into the variable
        self.variable.emit_buffer_read(f, line_prefix, tlv_out, error, 'self->' + self.variable_name)

        template = (
            '\n'
            '${lp}/* The remaining size of the buffer needs to be 0 if we successfully read the TLV */\n'
            '${lp}if ((offset = qmi_message_tlv_read_remaining_size (message, init_offset, offset)) > 0) {\n'
            '${lp}    g_warning ("Left \'%" G_GSIZE_FORMAT "\' bytes unread when getting the \'${name}\' TLV", offset);\n'
            '${lp}}\n'
            '\n'
            '${lp}self->${variable_name}_set = TRUE;\n'
            '\n'
            '${tlv_out}:\n')
        if self.mandatory:
            template += (
                '${lp}if (!self->${variable_name}_set) {\n'
                '${lp}    ${container_underscore}_unref (self);\n'
                '${lp}    return NULL;\n'
                '${lp}}\n')
        else:
            template += (
                '${lp};\n')
        f.write(string.Template(template).substitute(translations))


    """
    Emit the method responsible for creating a printable representation of the TLV
    """
    def emit_tlv_helpers(self, f):
        if TypeFactory.helpers_emitted(self.fullname):
            return

        TypeFactory.set_helpers_emitted(self.fullname)

        translations = { 'name'       : self.name,
                         'tlv_id'     : self.id_enum_name,
                         'underscore' : utils.build_underscore_name (self.fullname) }

        template = (
            '\n'
            'static gchar *\n'
            '${underscore}_get_printable (\n'
            '    QmiMessage *message,\n'
            '    const gchar *line_prefix)\n'
            '{\n'
            '    gsize offset = 0;\n'
            '    gsize init_offset;\n'
            '    GString *printable;\n'
            '    GError *error = NULL;\n'
            '\n'
            '    if ((init_offset = qmi_message_tlv_read_init (message, ${tlv_id}, NULL, NULL)) == 0)\n'
            '        return NULL;\n'
            '\n'
            '    printable = g_string_new ("");\n')
        f.write(string.Template(template).substitute(translations))

        # Now, read the contents of the buffer into the printable representation
        self.variable.emit_get_printable(f, '    ', self.personal_info)

        template = (
            '\n'
            '    if ((offset = qmi_message_tlv_read_remaining_size (message, init_offset, offset)) > 0)\n'
            '        g_string_append_printf (printable, "Additional unexpected \'%" G_GSIZE_FORMAT "\' bytes", offset);\n'
            '\n'
            'out:\n'
            '    if (error) {\n'
            '        g_string_append_printf (printable, " ERROR: %s", error->message);\n'
            '        g_error_free (error);\n'
            '    }\n'
            '    return g_string_free (printable, FALSE);\n'
            '}\n')
        f.write(string.Template(template).substitute(translations))


    """
    Add sections
    """
    def add_sections(self, sections):
        translations = { 'underscore'        : utils.build_underscore_name(self.name),
                         'prefix_camelcase'  : utils.build_camelcase_name(self.prefix),
                         'prefix_underscore' : utils.build_underscore_name(self.prefix) }

        if not TypeFactory.is_section_emitted(self.fullname):
            TypeFactory.set_section_emitted(self.fullname)
            self.variable.add_sections(sections)

        # Public methods
        template = (
            '${prefix_underscore}_get_${underscore}\n')
        if self.variable.needs_compat_gir and self.service != 'CTL':
            template += (
                '${prefix_underscore}_get_${underscore}_gir\n')
        if self.container_type == 'Input':
            template += (
                '${prefix_underscore}_set_${underscore}\n')
            if self.variable.needs_compat_gir and self.service != 'CTL':
                template += (
                    '${prefix_underscore}_set_${underscore}_gir\n')
        sections['public-methods'] += string.Template(template).substitute(translations)
