__license__ = """
NML is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.

NML is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License along
with NML; if not, write to the Free Software Foundation, Inc.,
51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA."""

from nml.ply import yacc

from nml import expression, generic, nmlop, tokens, unit
from nml.actions import actionD, real_sprite
from nml.ast import (
    alt_sprites,
    assignment,
    badgetable,
    base_graphics,
    basecost,
    cargotable,
    conditional,
    constant,
    deactivate,
    disable_item,
    error,
    font,
    general,
    grf,
    item,
    loop,
    override,
    produce,
    replace,
    skipall,
    snowline,
    sort_vehicles,
    spriteblock,
    switch,
    tilelayout,
    townnames,
    tracktypetable,
)

# Actions (p_* methods) access PLY's existing symbol slice directly, avoiding its indexed compatibility methods.
# Positions still use t.lineno() for nonterminals.
# Left-recursive lists are parser-owned until their enclosing rule reduces.


class NMLParser:
    """
    @ivar lexer: Scanner providing tokens.
    @type lexer: L{NMLLexer}

    @ivar tokens: Tokens of the scanner (used by PLY).
    @type tokens: C{List} of C{str}

    @ivar parser: PLY parser.
    @type parser: L{ply.yacc}
    """

    def __init__(self, debug=False):
        self.lexer = tokens.NMLLexer()
        self.lexer.build()
        self.tokens = self.lexer.tokens
        self.parser = yacc.yacc(
            module=self,
            debug=debug,
            optimize=not debug,
        )

    def parse(self, text, input_filename):
        self.lexer.setup(text, input_filename)
        return self.parser.parse(None, lexer=self.lexer.lexer)

    # operator precedence (lower in the list = higher priority)
    precedence = (
        ("left", "COMMA"),
        ("right", "TERNARY_OPEN", "COLON"),
        ("left", "LOGICAL_OR"),
        ("left", "LOGICAL_AND"),
        ("left", "OR"),
        ("left", "XOR"),
        ("left", "AND"),
        ("left", "COMP_EQ", "COMP_NEQ", "COMP_LE", "COMP_GE", "COMP_LT", "COMP_GT"),
        ("left", "SHIFT_LEFT", "SHIFT_RIGHT", "SHIFTU_RIGHT"),
        ("left", "PLUS", "MINUS"),
        ("left", "TIMES", "DIVIDE", "MODULO"),
        ("left", "LOGICAL_NOT", "BINARY_NOT"),
    )

    def p_error(self, t):
        if t is None:
            raise generic.ScriptError("Syntax error, unexpected end-of-file")
        else:
            raise generic.ScriptError('Syntax error, unexpected token "{}"'.format(t.value), t.lineno)

    #
    # Main script blocks
    #
    def p_main_script(self, t):
        "main_script : script"
        symbols = t.slice
        symbols[0].value = general.MainScript(symbols[1].value)

    # Append in place to avoid repeatedly copying the growing prefix.
    def p_script(self, t):
        """script :
        | script main_block"""
        symbols = t.slice
        if len(symbols) == 1:
            symbols[0].value = []
        else:
            symbols[1].value.append(symbols[2].value)
            symbols[0].value = symbols[1].value

    def p_main_block(self, t):
        """main_block : switch
        | random_switch
        | produce
        | spriteset
        | spritegroup
        | spritelayout
        | template_declaration
        | tilelayout
        | town_names
        | badgetable
        | cargotable
        | railtype
        | roadtype
        | tramtype
        | grf_block
        | param_assignment
        | skip_all
        | conditional
        | loop
        | item
        | property_block
        | graphics_block
        | liveryoverride_block
        | error_block
        | disable_item
        | deactivate
        | replace
        | replace_new
        | base_graphics
        | font_glyph
        | alt_sprites
        | snowline
        | engine_override
        | sort_vehicles
        | basecost
        | constant"""
        symbols = t.slice
        symbols[0].value = symbols[1].value

    #
    # Expressions
    #
    def p_expression(self, t):
        """expression : NUMBER
        | FLOAT
        | param
        | variable
        | ID
        | STRING_LITERAL
        | string"""
        symbols = t.slice
        symbols[0].value = symbols[1].value

    def p_parenthesed_expression(self, t):
        "expression : LPAREN expression RPAREN"
        symbols = t.slice
        symbols[0].value = symbols[2].value

    def p_parameter(self, t):
        "param : PARAMETER LBRACKET expression RBRACKET"
        symbols = t.slice
        symbols[0].value = expression.Parameter(symbols[3].value, t.lineno(1), True)

    def p_parameter_other_grf(self, t):
        "param : PARAMETER LBRACKET expression COMMA expression RBRACKET"
        symbols = t.slice
        symbols[0].value = expression.OtherGRFParameter(symbols[3].value, symbols[5].value, t.lineno(1))

    code_to_op = {
        "+": nmlop.ADD,
        "-": nmlop.SUB,
        "*": nmlop.MUL,
        "/": nmlop.DIV,
        "%": nmlop.MOD,
        "&": nmlop.AND,
        "|": nmlop.OR,
        "^": nmlop.XOR,
        "&&": nmlop.AND,
        "||": nmlop.OR,
        "==": nmlop.CMP_EQ,
        "!=": nmlop.CMP_NEQ,
        "<=": nmlop.CMP_LE,
        ">=": nmlop.CMP_GE,
        "<": nmlop.CMP_LT,
        ">": nmlop.CMP_GT,
        "<<": nmlop.SHIFT_LEFT,
        ">>": nmlop.SHIFT_RIGHT,
        ">>>": nmlop.SHIFTU_RIGHT,
    }

    def p_binop(self, t):
        """expression : expression PLUS expression
        | expression MINUS expression
        | expression TIMES expression
        | expression DIVIDE expression
        | expression MODULO expression
        | expression AND expression
        | expression OR expression
        | expression XOR expression
        | expression SHIFT_LEFT expression
        | expression SHIFT_RIGHT expression
        | expression SHIFTU_RIGHT expression
        | expression COMP_EQ expression
        | expression COMP_NEQ expression
        | expression COMP_LE expression
        | expression COMP_GE expression
        | expression COMP_LT expression
        | expression COMP_GT expression"""
        symbols = t.slice
        symbols[0].value = expression.BinOp(
            self.code_to_op[symbols[2].value], symbols[1].value, symbols[3].value, symbols[1].value.pos
        )

    def p_binop_logical(self, t):
        """expression : expression LOGICAL_AND expression
        | expression LOGICAL_OR expression"""
        symbols = t.slice
        symbols[0].value = expression.BinOp(
            self.code_to_op[symbols[2].value],
            expression.Boolean(symbols[1].value),
            expression.Boolean(symbols[3].value),
            symbols[1].value.pos,
        )

    def p_logical_not(self, t):
        "expression : LOGICAL_NOT expression"
        symbols = t.slice
        symbols[0].value = expression.Not(expression.Boolean(symbols[2].value), t.lineno(1))

    def p_binary_not(self, t):
        "expression : BINARY_NOT expression"
        symbols = t.slice
        symbols[0].value = expression.BinNot(symbols[2].value, t.lineno(1))

    def p_ternary_op(self, t):
        "expression : expression TERNARY_OPEN expression COLON expression"
        symbols = t.slice
        symbols[0].value = expression.TernaryOp(
            symbols[1].value, symbols[3].value, symbols[5].value, symbols[1].value.pos
        )

    def p_unary_minus(self, t):
        "expression : MINUS expression"
        symbols = t.slice
        symbols[0].value = nmlop.SUB(0, symbols[2].value, t.lineno(1))

    def p_variable(self, t):
        "variable : VARIABLE LBRACKET expression_list RBRACKET"
        symbols = t.slice
        symbols[0].value = expression.Variable(*symbols[3].value)
        symbols[0].value.pos = t.lineno(1)

    def p_function(self, t):
        "expression : ID LPAREN expression_list RPAREN"
        symbols = t.slice
        symbols[0].value = expression.FunctionCall(symbols[1].value, symbols[3].value, symbols[1].value.pos)

    def p_array(self, t):
        "expression : LBRACKET expression_list RBRACKET"
        symbols = t.slice
        symbols[0].value = expression.Array(symbols[2].value, t.lineno(1))

    #
    # Commonly used non-terminals that are not expressions
    #
    def p_assignment_list(self, t):
        """assignment_list : assignment
        | param_desc
        | assignment_list assignment
        | assignment_list param_desc"""
        symbols = t.slice
        if len(symbols) == 2:
            symbols[0].value = [symbols[1].value]
        else:
            symbols[1].value.append(symbols[2].value)
            symbols[0].value = symbols[1].value

    def p_assignment(self, t):
        "assignment : ID COLON expression SEMICOLON"
        symbols = t.slice
        symbols[0].value = assignment.Assignment(symbols[1].value, symbols[3].value, symbols[1].value.pos)

    def p_param_desc(self, t):
        """param_desc : PARAMETER expression LBRACE setting_list RBRACE
        | PARAMETER LBRACE setting_list RBRACE"""
        symbols = t.slice
        if len(symbols) == 5:
            symbols[0].value = grf.ParameterDescription(symbols[3].value)
        else:
            symbols[0].value = grf.ParameterDescription(symbols[4].value, symbols[2].value)

    def p_setting_list(self, t):
        """setting_list : setting
        | setting_list setting"""
        symbols = t.slice
        if len(symbols) == 2:
            symbols[0].value = [symbols[1].value]
        else:
            symbols[1].value.append(symbols[2].value)
            symbols[0].value = symbols[1].value

    def p_setting(self, t):
        "setting : ID LBRACE setting_value_list RBRACE"
        symbols = t.slice
        symbols[0].value = grf.ParameterSetting(symbols[1].value, symbols[3].value)

    def p_setting_value_list(self, t):
        """setting_value_list : setting_value
        | setting_value_list setting_value"""
        symbols = t.slice
        if len(symbols) == 2:
            symbols[0].value = [symbols[1].value]
        else:
            symbols[1].value.append(symbols[2].value)
            symbols[0].value = symbols[1].value

    def p_setting_value(self, t):
        "setting_value : assignment"
        symbols = t.slice
        symbols[0].value = symbols[1].value

    def p_names_setting_value(self, t):
        "setting_value : ID COLON LBRACE name_string_list RBRACE SEMICOLON"
        symbols = t.slice
        symbols[0].value = assignment.Assignment(symbols[1].value, symbols[4].value, symbols[1].value.pos)

    def p_name_string_list(self, t):
        """name_string_list : name_string_item
        | name_string_list name_string_item"""
        symbols = t.slice
        if len(symbols) == 2:
            symbols[0].value = expression.Array([symbols[1].value], symbols[1].value.pos)
        else:
            symbols[1].value.values.append(symbols[2].value)
            symbols[0].value = symbols[1].value

    def p_name_string_item(self, t):
        "name_string_item : expression COLON string SEMICOLON"
        symbols = t.slice
        symbols[0].value = assignment.Assignment(symbols[1].value, symbols[3].value, symbols[1].value.pos)

    def p_string(self, t):
        "string : STRING LPAREN expression_list RPAREN"
        symbols = t.slice
        symbols[0].value = expression.String(symbols[3].value, t.lineno(1))

    def p_non_empty_expression_list(self, t):
        """non_empty_expression_list : expression
        | non_empty_expression_list COMMA expression"""
        symbols = t.slice
        if len(symbols) == 2:
            symbols[0].value = [symbols[1].value]
        else:
            symbols[1].value.append(symbols[3].value)
            symbols[0].value = symbols[1].value

    def p_expression_list(self, t):
        """expression_list :
        | non_empty_expression_list
        | non_empty_expression_list COMMA"""
        symbols = t.slice
        symbols[0].value = [] if len(symbols) == 1 else symbols[1].value

    def p_non_empty_id_list(self, t):
        """non_empty_id_list : ID
        | non_empty_id_list COMMA ID"""
        symbols = t.slice
        if len(symbols) == 2:
            symbols[0].value = [symbols[1].value]
        else:
            symbols[1].value.append(symbols[3].value)
            symbols[0].value = symbols[1].value

    def p_id_list(self, t):
        """id_list :
        | non_empty_id_list
        | non_empty_id_list COMMA"""
        symbols = t.slice
        symbols[0].value = [] if len(symbols) == 1 else symbols[1].value

    def p_generic_assignment(self, t):
        "generic_assignment : expression COLON expression SEMICOLON"
        symbols = t.slice
        symbols[0].value = assignment.Assignment(symbols[1].value, symbols[3].value, t.lineno(1))

    def p_generic_assignment_list(self, t):
        """generic_assignment_list :
        | generic_assignment_list generic_assignment"""
        symbols = t.slice
        if len(symbols) == 1:
            symbols[0].value = []
        else:
            symbols[1].value.append(symbols[2].value)
            symbols[0].value = symbols[1].value

    def p_snowline_assignment(self, t):
        """snowline_assignment : expression COLON expression SEMICOLON
        | expression COLON expression UNIT SEMICOLON"""
        symbols = t.slice
        unit_value = None if len(symbols) == 5 else unit.get_unit(symbols[4].value)
        symbols[0].value = assignment.UnitAssignment(symbols[1].value, symbols[3].value, unit_value, t.lineno(1))

    def p_snowline_assignment_list(self, t):
        """snowline_assignment_list :
        | snowline_assignment_list snowline_assignment"""
        symbols = t.slice
        if len(symbols) == 1:
            symbols[0].value = []
        else:
            symbols[1].value.append(symbols[2].value)
            symbols[0].value = symbols[1].value

    #
    # Item blocks
    #
    def p_item(self, t):
        "item : ITEM LPAREN expression_list RPAREN LBRACE script RBRACE"
        symbols = t.slice
        symbols[0].value = item.Item(symbols[3].value, symbols[6].value, t.lineno(1))

    def p_property_block(self, t):
        "property_block : PROPERTY LBRACE property_list RBRACE"
        symbols = t.slice
        symbols[0].value = item.PropertyBlock(symbols[3].value, t.lineno(1))

    def p_property_list(self, t):
        """property_list : property_assignment
        | property_list property_assignment"""
        symbols = t.slice
        if len(symbols) == 2:
            symbols[0].value = [symbols[1].value]
        else:
            symbols[1].value.append(symbols[2].value)
            symbols[0].value = symbols[1].value

    def p_property_assignment(self, t):
        """property_assignment : ID COLON expression SEMICOLON
        | ID COLON expression UNIT SEMICOLON
        | NUMBER COLON expression SEMICOLON
        | NUMBER COLON expression UNIT SEMICOLON"""
        symbols = t.slice
        name = symbols[1].value
        unit_value = None if len(symbols) == 5 else unit.get_unit(symbols[4].value)
        symbols[0].value = item.Property(name, symbols[3].value, unit_value, t.lineno(1))

    def p_graphics_block(self, t):
        "graphics_block : GRAPHICS LBRACE graphics_list RBRACE"
        symbols = t.slice
        symbols[0].value = item.GraphicsBlock(symbols[3].value[0], symbols[3].value[1], t.lineno(1))

    def p_liveryoverride_block(self, t):
        "liveryoverride_block : LIVERYOVERRIDE LPAREN expression RPAREN LBRACE graphics_list RBRACE"
        symbols = t.slice
        symbols[0].value = item.LiveryOverride(
            symbols[3].value, item.GraphicsBlock(symbols[6].value[0], symbols[6].value[1], t.lineno(1)), t.lineno(1)
        )

    def p_graphics_list(self, t):
        """graphics_list : graphics_assignment_list
        | graphics_assignment_list switch_value
        | switch_value"""
        # Save graphics block as a tuple, we need to add position info later
        symbols = t.slice
        if len(symbols) == 2:
            if isinstance(symbols[1].value, list):
                symbols[0].value = (symbols[1].value, None)
            else:
                symbols[0].value = ([], symbols[1].value)
        else:
            symbols[0].value = (symbols[1].value, symbols[2].value)

    def p_graphics_assignment(self, t):
        "graphics_assignment : expression COLON switch_value"
        symbols = t.slice
        symbols[0].value = item.GraphicsDefinition(symbols[1].value, symbols[3].value)

    def p_graphics_assignment_list(self, t):
        """graphics_assignment_list : graphics_assignment
        | graphics_assignment_list graphics_assignment"""
        symbols = t.slice
        if len(symbols) == 2:
            symbols[0].value = [symbols[1].value]
        else:
            symbols[1].value.append(symbols[2].value)
            symbols[0].value = symbols[1].value

    #
    # Program flow control (if/else/while)
    #
    def p_conditional(self, t):
        """conditional : if_else_parts
        | if_else_parts else_block"""
        symbols = t.slice
        parts = symbols[1].value
        if len(symbols) > 2:
            parts.append(symbols[2].value)
        symbols[0].value = conditional.ConditionalList(parts)

    def p_else_block(self, t):
        "else_block : ELSE LBRACE script RBRACE"
        symbols = t.slice
        symbols[0].value = conditional.Conditional(None, symbols[3].value, t.lineno(1))

    def p_if_else_parts(self, t):
        """if_else_parts : IF LPAREN expression RPAREN LBRACE script RBRACE
        | if_else_parts ELSE IF LPAREN expression RPAREN LBRACE script RBRACE"""
        symbols = t.slice
        if len(symbols) == 8:
            symbols[0].value = [conditional.Conditional(symbols[3].value, symbols[6].value, t.lineno(1))]
        else:
            symbols[1].value.append(conditional.Conditional(symbols[5].value, symbols[8].value, t.lineno(2)))
            symbols[0].value = symbols[1].value

    def p_loop(self, t):
        "loop : WHILE LPAREN expression RPAREN LBRACE script RBRACE"
        symbols = t.slice
        symbols[0].value = loop.Loop(symbols[3].value, symbols[6].value, t.lineno(1))

    #
    # (Random) Switch block
    #
    def p_switch(self, t):
        "switch : SWITCH LPAREN expression_list RPAREN LBRACE switch_body RBRACE"
        symbols = t.slice
        symbols[0].value = switch.Switch(symbols[3].value, symbols[6].value, t.lineno(1))

    def p_switch_body(self, t):
        """switch_body : switch_ranges switch_value
        | switch_ranges"""
        symbols = t.slice
        symbols[0].value = switch.SwitchBody(symbols[1].value, symbols[2].value if len(symbols) == 3 else None)

    def p_switch_ranges(self, t):
        """switch_ranges :
        | switch_ranges expression COLON switch_value
        | switch_ranges expression UNIT COLON switch_value
        | switch_ranges expression RANGE expression COLON switch_value
        | switch_ranges expression RANGE expression UNIT COLON switch_value"""
        symbols = t.slice
        if len(symbols) == 1:
            symbols[0].value = []
        elif len(symbols) == 5:
            symbols[1].value.append(switch.SwitchRange(symbols[2].value, symbols[2].value, symbols[4].value))
            symbols[0].value = symbols[1].value
        elif len(symbols) == 6:
            symbols[1].value.append(
                switch.SwitchRange(symbols[2].value, symbols[2].value, symbols[5].value, symbols[3].value)
            )
            symbols[0].value = symbols[1].value
        elif len(symbols) == 7:
            symbols[1].value.append(switch.SwitchRange(symbols[2].value, symbols[4].value, symbols[6].value))
            symbols[0].value = symbols[1].value
        else:
            symbols[1].value.append(
                switch.SwitchRange(symbols[2].value, symbols[4].value, symbols[7].value, symbols[5].value)
            )
            symbols[0].value = symbols[1].value

    def p_switch_value(self, t):
        """switch_value : RETURN expression SEMICOLON
        | RETURN SEMICOLON
        | expression SEMICOLON"""
        symbols = t.slice
        if len(symbols) == 4:
            symbols[0].value = switch.SwitchValue(symbols[2].value, True, symbols[2].value.pos)
        elif symbols[1].value == "return":
            symbols[0].value = switch.SwitchValue(None, True, t.lineno(1))
        else:
            symbols[0].value = switch.SwitchValue(symbols[1].value, False, symbols[1].value.pos)

    def p_random_switch(self, t):
        "random_switch : RANDOMSWITCH LPAREN expression_list RPAREN LBRACE random_body RBRACE"
        symbols = t.slice
        symbols[0].value = switch.RandomSwitch(symbols[3].value, symbols[6].value, t.lineno(1))

    def p_random_body(self, t):
        """random_body :
        | random_body expression COLON switch_value"""
        symbols = t.slice
        if len(symbols) == 1:
            symbols[0].value = []
        else:
            symbols[1].value.append(switch.RandomChoice(symbols[2].value, symbols[4].value))
            symbols[0].value = symbols[1].value

    def p_produce_cargo_list(self, t):
        """produce_cargo_list : LBRACKET RBRACKET
        | LBRACKET setting_value_list RBRACKET"""
        symbols = t.slice
        if len(symbols) == 3:
            symbols[0].value = []
        else:
            symbols[0].value = symbols[2].value

    def p_produce(self, t):
        """produce : PRODUCE LPAREN ID COMMA expression_list RPAREN SEMICOLON
        | PRODUCE LPAREN ID COMMA produce_cargo_list COMMA produce_cargo_list COMMA expression RPAREN
        | PRODUCE LPAREN ID COMMA produce_cargo_list COMMA produce_cargo_list RPAREN"""
        symbols = t.slice
        if len(symbols) == 8:
            symbols[0].value = produce.ProduceOld([symbols[3].value] + symbols[5].value, t.lineno(1))
        elif len(symbols) == 11:
            symbols[0].value = produce.Produce(
                symbols[3].value, symbols[5].value, symbols[7].value, symbols[9].value, t.lineno(1)
            )
        else:
            symbols[0].value = produce.Produce(
                symbols[3].value, symbols[5].value, symbols[7].value, expression.ConstantNumeric(0), t.lineno(1)
            )

    #
    # Real sprites and related stuff
    #
    def p_real_sprite(self, t):
        """real_sprite : LBRACKET expression_list RBRACKET
        | ID COLON LBRACKET expression_list RBRACKET"""
        symbols = t.slice
        if len(symbols) == 4:
            symbols[0].value = real_sprite.RealSprite(param_list=symbols[2].value, poslist=[t.lineno(1)])
        else:
            symbols[0].value = real_sprite.RealSprite(
                param_list=symbols[4].value, label=symbols[1].value, poslist=[t.lineno(1)]
            )

    def p_recolour_assignment_list(self, t):
        """recolour_assignment_list :
        | recolour_assignment_list recolour_assignment"""
        symbols = t.slice
        if len(symbols) == 1:
            symbols[0].value = []
        else:
            symbols[1].value.append(symbols[2].value)
            symbols[0].value = symbols[1].value

    def p_recolour_assignment_1(self, t):
        "recolour_assignment : expression COLON expression SEMICOLON"
        symbols = t.slice
        symbols[0].value = assignment.Assignment(
            assignment.Range(symbols[1].value, None), assignment.Range(symbols[3].value, None), symbols[1].value.pos
        )

    def p_recolour_assignment_2(self, t):
        "recolour_assignment : expression RANGE expression COLON expression RANGE expression SEMICOLON"
        symbols = t.slice
        symbols[0].value = assignment.Assignment(
            assignment.Range(symbols[1].value, symbols[3].value),
            assignment.Range(symbols[5].value, symbols[7].value),
            symbols[1].value.pos,
        )

    def p_recolour_assignment_3(self, t):
        "recolour_assignment : expression RANGE expression COLON expression SEMICOLON"
        symbols = t.slice
        symbols[0].value = assignment.Assignment(
            assignment.Range(symbols[1].value, symbols[3].value),
            assignment.Range(symbols[5].value, None),
            symbols[1].value.pos,
        )

    def p_recolour_sprite(self, t):
        """real_sprite : RECOLOUR_SPRITE LBRACE recolour_assignment_list RBRACE
        | ID COLON RECOLOUR_SPRITE LBRACE recolour_assignment_list RBRACE"""
        symbols = t.slice
        if len(symbols) == 5:
            symbols[0].value = real_sprite.RecolourSprite(mapping=symbols[3].value, poslist=[t.lineno(1)])
        else:
            symbols[0].value = real_sprite.RecolourSprite(
                mapping=symbols[5].value, label=symbols[1].value, poslist=[t.lineno(1)]
            )

    def p_template_declaration(self, t):
        "template_declaration : TEMPLATE ID LPAREN id_list RPAREN LBRACE spriteset_contents RBRACE"
        symbols = t.slice
        symbols[0].value = spriteblock.TemplateDeclaration(
            symbols[2].value, symbols[4].value, symbols[7].value, t.lineno(1)
        )

    def p_template_usage(self, t):
        """template_usage : ID LPAREN expression_list RPAREN
        | ID COLON ID LPAREN expression_list RPAREN"""
        symbols = t.slice
        if len(symbols) == 5:
            symbols[0].value = real_sprite.TemplateUsage(symbols[1].value, symbols[3].value, None, t.lineno(1))
        else:
            symbols[0].value = real_sprite.TemplateUsage(
                symbols[3].value, symbols[5].value, symbols[1].value, t.lineno(1)
            )

    def p_spriteset_contents(self, t):
        """spriteset_contents : real_sprite
        | template_usage
        | spriteset_contents real_sprite
        | spriteset_contents template_usage"""
        symbols = t.slice
        if len(symbols) == 2:
            symbols[0].value = [symbols[1].value]
        else:
            symbols[1].value.append(symbols[2].value)
            symbols[0].value = symbols[1].value

    def p_replace(self, t):
        """replace : REPLACESPRITE LPAREN expression_list RPAREN LBRACE spriteset_contents RBRACE
        | REPLACESPRITE ID LPAREN expression_list RPAREN LBRACE spriteset_contents RBRACE"""
        symbols = t.slice
        if len(symbols) == 9:
            symbols[0].value = replace.ReplaceSprite(symbols[4].value, symbols[7].value, symbols[2].value, t.lineno(1))
        else:
            symbols[0].value = replace.ReplaceSprite(symbols[3].value, symbols[6].value, None, t.lineno(1))

    def p_replace_new(self, t):
        """replace_new : REPLACENEWSPRITE LPAREN expression_list RPAREN LBRACE spriteset_contents RBRACE
        | REPLACENEWSPRITE ID LPAREN expression_list RPAREN LBRACE spriteset_contents RBRACE"""
        symbols = t.slice
        if len(symbols) == 9:
            symbols[0].value = replace.ReplaceNewSprite(
                symbols[4].value, symbols[7].value, symbols[2].value, t.lineno(1)
            )
        else:
            symbols[0].value = replace.ReplaceNewSprite(symbols[3].value, symbols[6].value, None, t.lineno(1))

    def p_base_graphics(self, t):
        """base_graphics : BASE_GRAPHICS LPAREN expression_list RPAREN LBRACE spriteset_contents RBRACE
        | BASE_GRAPHICS ID LPAREN expression_list RPAREN LBRACE spriteset_contents RBRACE"""
        symbols = t.slice
        if len(symbols) == 9:
            symbols[0].value = base_graphics.BaseGraphics(
                symbols[4].value, symbols[7].value, symbols[2].value, t.lineno(1)
            )
        else:
            symbols[0].value = base_graphics.BaseGraphics(symbols[3].value, symbols[6].value, None, t.lineno(1))

    def p_font_glyph(self, t):
        """font_glyph : FONTGLYPH LPAREN expression_list RPAREN LBRACE spriteset_contents RBRACE
        | FONTGLYPH ID LPAREN expression_list RPAREN LBRACE spriteset_contents RBRACE"""
        symbols = t.slice
        if len(symbols) == 9:
            symbols[0].value = font.FontGlyphBlock(symbols[4].value, symbols[7].value, symbols[2].value, t.lineno(1))
        else:
            symbols[0].value = font.FontGlyphBlock(symbols[3].value, symbols[6].value, None, t.lineno(1))

    def p_alt_sprites(self, t):
        "alt_sprites : ALT_SPRITES LPAREN expression_list RPAREN LBRACE spriteset_contents RBRACE"
        symbols = t.slice
        symbols[0].value = alt_sprites.AltSpritesBlock(symbols[3].value, symbols[6].value, t.lineno(1))

    #
    # Sprite sets/groups and such
    #

    def p_spriteset(self, t):
        "spriteset : SPRITESET LPAREN expression_list RPAREN LBRACE spriteset_contents RBRACE"
        symbols = t.slice
        symbols[0].value = spriteblock.SpriteSet(symbols[3].value, symbols[6].value, t.lineno(1))

    def p_spritegroup_normal(self, t):
        "spritegroup : SPRITEGROUP ID LBRACE spriteview_list RBRACE"
        symbols = t.slice
        symbols[0].value = spriteblock.SpriteGroup(symbols[2].value, symbols[4].value, t.lineno(1))

    def p_spritelayout(self, t):
        """spritelayout : SPRITELAYOUT ID LBRACE layout_sprite_list RBRACE
        | SPRITELAYOUT ID LPAREN id_list RPAREN LBRACE layout_sprite_list RBRACE"""
        symbols = t.slice
        if len(symbols) == 6:
            symbols[0].value = spriteblock.SpriteLayout(symbols[2].value, [], symbols[4].value, t.lineno(1))
        else:
            symbols[0].value = spriteblock.SpriteLayout(
                symbols[2].value, symbols[4].value, symbols[7].value, t.lineno(1)
            )

    def p_spriteview_list(self, t):
        """spriteview_list :
        | spriteview_list spriteview"""
        symbols = t.slice
        if len(symbols) == 1:
            symbols[0].value = []
        else:
            symbols[1].value.append(symbols[2].value)
            symbols[0].value = symbols[1].value

    def p_spriteview(self, t):
        """spriteview : ID COLON LBRACKET expression_list RBRACKET SEMICOLON
        | ID COLON expression SEMICOLON"""
        symbols = t.slice
        if len(symbols) == 7:
            symbols[0].value = spriteblock.SpriteView(symbols[1].value, symbols[4].value, t.lineno(1))
        else:
            symbols[0].value = spriteblock.SpriteView(symbols[1].value, [symbols[3].value], t.lineno(1))

    def p_layout_sprite_list(self, t):
        """layout_sprite_list :
        | layout_sprite_list layout_sprite"""
        symbols = t.slice
        if len(symbols) == 1:
            symbols[0].value = []
        else:
            symbols[1].value.append(symbols[2].value)
            symbols[0].value = symbols[1].value

    def p_layout_sprite(self, t):
        "layout_sprite : ID LBRACE layout_param_list RBRACE"
        symbols = t.slice
        symbols[0].value = spriteblock.LayoutSprite(symbols[1].value, symbols[3].value, t.lineno(1))

    def p_layout_param_list(self, t):
        """layout_param_list : assignment
        | layout_param_list assignment"""
        symbols = t.slice
        if len(symbols) == 2:
            symbols[0].value = [symbols[1].value]
        else:
            symbols[1].value.append(symbols[2].value)
            symbols[0].value = symbols[1].value

    #
    # Town names
    #
    def p_town_names(self, t):
        """town_names : TOWN_NAMES LPAREN expression RPAREN LBRACE town_names_param_list RBRACE
        | TOWN_NAMES LBRACE town_names_param_list RBRACE"""
        symbols = t.slice
        if len(symbols) == 8:
            symbols[0].value = townnames.TownNames(symbols[3].value, symbols[6].value, t.lineno(1))
        else:
            symbols[0].value = townnames.TownNames(None, symbols[3].value, t.lineno(1))

    def p_town_names_param_list(self, t):
        """town_names_param_list : town_names_param
        | town_names_param_list town_names_param"""
        symbols = t.slice
        if len(symbols) == 2:
            symbols[0].value = [symbols[1].value]
        else:
            symbols[1].value.append(symbols[2].value)
            symbols[0].value = symbols[1].value

    def p_town_names_param(self, t):
        """town_names_param : ID COLON string SEMICOLON
        | LBRACE town_names_part_list RBRACE
        | LBRACE town_names_part_list COMMA RBRACE"""
        symbols = t.slice
        if symbols[1].value != "{":
            symbols[0].value = townnames.TownNamesParam(symbols[1].value, symbols[3].value, t.lineno(1))
        else:
            symbols[0].value = townnames.TownNamesPart(symbols[2].value, t.lineno(1))

    def p_town_names_part_list(self, t):
        """town_names_part_list : town_names_part
        | town_names_part_list COMMA town_names_part"""
        symbols = t.slice
        if len(symbols) == 2:
            symbols[0].value = [symbols[1].value]
        else:
            symbols[1].value.append(symbols[3].value)
            symbols[0].value = symbols[1].value

    def p_town_names_part(self, t):
        """town_names_part : TOWN_NAMES LPAREN expression COMMA expression RPAREN
        | ID LPAREN STRING_LITERAL COMMA expression RPAREN"""
        symbols = t.slice
        if symbols[1].value == "town_names":
            symbols[0].value = townnames.TownNamesEntryDefinition(symbols[3].value, symbols[5].value, t.lineno(1))
        else:
            symbols[0].value = townnames.TownNamesEntryText(
                symbols[1].value, symbols[3].value, symbols[5].value, t.lineno(1)
            )

    #
    # Snow line
    #
    def p_snowline(self, t):
        "snowline : SNOWLINE LPAREN ID RPAREN LBRACE snowline_assignment_list RBRACE"
        symbols = t.slice
        symbols[0].value = snowline.Snowline(symbols[3].value, symbols[6].value, t.lineno(1))

    #
    # Various misc. main script blocks that don't belong anywhere else
    #
    def p_param_assignment(self, t):
        "param_assignment : expression EQ expression SEMICOLON"
        symbols = t.slice
        symbols[0].value = actionD.ParameterAssignment(symbols[1].value, symbols[3].value)

    def p_error_block(self, t):
        "error_block : ERROR LPAREN expression_list RPAREN SEMICOLON"
        symbols = t.slice
        symbols[0].value = error.Error(symbols[3].value, t.lineno(1))

    def p_disable_item(self, t):
        "disable_item : DISABLE_ITEM LPAREN expression_list RPAREN SEMICOLON"
        symbols = t.slice
        symbols[0].value = disable_item.DisableItem(symbols[3].value, t.lineno(1))

    def p_badgetable(self, t):
        """badgetable : BADGETABLE LBRACE badgetable_list RBRACE
        | BADGETABLE LBRACE badgetable_list COMMA RBRACE"""
        symbols = t.slice
        symbols[0].value = badgetable.BadgeTable(symbols[3].value, t.lineno(1))

    def p_badgetable_list(self, t):
        """badgetable_list : ID
        | STRING_LITERAL
        | badgetable_list COMMA ID
        | badgetable_list COMMA STRING_LITERAL"""
        symbols = t.slice
        if len(symbols) == 2:
            symbols[0].value = [symbols[1].value]
        else:
            symbols[1].value.append(symbols[3].value)
            symbols[0].value = symbols[1].value

    def p_cargotable(self, t):
        """cargotable : CARGOTABLE LBRACE cargotable_list RBRACE
        | CARGOTABLE LBRACE cargotable_list COMMA RBRACE"""
        symbols = t.slice
        symbols[0].value = cargotable.CargoTable(symbols[3].value, t.lineno(1))

    def p_cargotable_list(self, t):
        """cargotable_list : ID
        | STRING_LITERAL
        | cargotable_list COMMA ID
        | cargotable_list COMMA STRING_LITERAL"""
        symbols = t.slice
        if len(symbols) == 2:
            symbols[0].value = [symbols[1].value]
        else:
            symbols[1].value.append(symbols[3].value)
            symbols[0].value = symbols[1].value

    def p_railtypetable(self, t):
        """railtype : RAILTYPETABLE LBRACE tracktypetable_list RBRACE
        | RAILTYPETABLE LBRACE tracktypetable_list COMMA RBRACE"""
        symbols = t.slice
        symbols[0].value = tracktypetable.RailtypeTable(symbols[3].value, t.lineno(1))

    def p_roadtypetable(self, t):
        """roadtype : ROADTYPETABLE LBRACE tracktypetable_list RBRACE
        | ROADTYPETABLE LBRACE tracktypetable_list COMMA RBRACE"""
        symbols = t.slice
        symbols[0].value = tracktypetable.RoadtypeTable(symbols[3].value, t.lineno(1))

    def p_tramtypetable(self, t):
        """tramtype : TRAMTYPETABLE LBRACE tracktypetable_list RBRACE
        | TRAMTYPETABLE LBRACE tracktypetable_list COMMA RBRACE"""
        symbols = t.slice
        symbols[0].value = tracktypetable.TramtypeTable(symbols[3].value, t.lineno(1))

    def p_tracktypetable_list(self, t):
        """tracktypetable_list : tracktypetable_item
        | tracktypetable_list COMMA tracktypetable_item"""
        symbols = t.slice
        if len(symbols) == 2:
            symbols[0].value = [symbols[1].value]
        else:
            symbols[1].value.append(symbols[3].value)
            symbols[0].value = symbols[1].value

    def p_tracktypetable_item(self, t):
        """tracktypetable_item : ID
        | STRING_LITERAL
        | ID COLON LBRACKET expression_list RBRACKET"""
        symbols = t.slice
        if len(symbols) == 2:
            symbols[0].value = symbols[1].value
        else:
            symbols[0].value = assignment.Assignment(symbols[1].value, symbols[4].value, symbols[1].value.pos)

    def p_basecost(self, t):
        "basecost : BASECOST LBRACE generic_assignment_list RBRACE"
        symbols = t.slice
        symbols[0].value = basecost.BaseCost(symbols[3].value, t.lineno(1))

    def p_deactivate(self, t):
        "deactivate : DEACTIVATE LPAREN expression_list RPAREN SEMICOLON"
        symbols = t.slice
        symbols[0].value = deactivate.DeactivateBlock(symbols[3].value, t.lineno(1))

    def p_grf_block(self, t):
        "grf_block : GRF LBRACE assignment_list RBRACE"
        symbols = t.slice
        symbols[0].value = grf.GRF(symbols[3].value, t.lineno(1))

    def p_skip_all(self, t):
        "skip_all : SKIP_ALL SEMICOLON"
        symbols = t.slice
        symbols[0].value = skipall.SkipAll(t.lineno(1))

    def p_engine_override(self, t):
        "engine_override : ENGINE_OVERRIDE LPAREN expression_list RPAREN SEMICOLON"
        symbols = t.slice
        symbols[0].value = override.EngineOverride(symbols[3].value, t.lineno(1))

    def p_sort_vehicles(self, t):
        "sort_vehicles : SORT_VEHICLES LPAREN expression_list RPAREN SEMICOLON"
        symbols = t.slice
        symbols[0].value = sort_vehicles.SortVehicles(symbols[3].value, t.lineno(1))

    def p_tilelayout(self, t):
        "tilelayout : TILELAYOUT ID LBRACE tilelayout_list RBRACE"
        symbols = t.slice
        symbols[0].value = tilelayout.TileLayout(symbols[2].value, symbols[4].value, t.lineno(1))

    def p_tilelayout_list(self, t):
        """tilelayout_list : tilelayout_item
        | tilelayout_list tilelayout_item"""
        symbols = t.slice
        if len(symbols) == 2:
            symbols[0].value = [symbols[1].value]
        else:
            symbols[1].value.append(symbols[2].value)
            symbols[0].value = symbols[1].value

    def p_tilelayout_item_tile(self, t):
        "tilelayout_item : expression COMMA expression COLON expression SEMICOLON"
        symbols = t.slice
        symbols[0].value = tilelayout.LayoutTile(symbols[1].value, symbols[3].value, symbols[5].value)

    def p_tilelayout_item_prop(self, t):
        "tilelayout_item : assignment"
        symbols = t.slice
        symbols[0].value = symbols[1].value

    def p_constant(self, t):
        "constant : CONST expression EQ expression SEMICOLON"
        symbols = t.slice
        symbols[0].value = constant.Constant(symbols[2].value, symbols[4].value)
