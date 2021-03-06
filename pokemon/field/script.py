
import imp
import itertools
import json
import os
import warnings

from compileengine import Decompiler, Variable, ExpressionBlock
from compileengine.engine import Engine, Function, VariableCollection, FunctionCollection
import six

from generic import Editable
from util.io import BinaryIO


class CommandMetaRegistry(type):
    """Tracks the creation of Command derived classes
    """
    command_classes = {}

    def __new__(cls, name, parents, attrs):
        new_cls = type.__new__(cls, name, parents, attrs)
        if name in CommandMetaRegistry.command_classes:
            raise NameError('{0} is already a command class'.format(name))
        CommandMetaRegistry.command_classes[name] = new_cls
        return new_cls


class CommandRet(object):
    __slots__ = ('command',
                 'args',
                 'current_arg',
                 'final')

    def __init__(self, command):
        self.command = command
        self.args = []
        self.current_arg = self.command.returns[0]
        self.final = True

    def __iter__(self):
        self.final = False
        for ret_idx in self.command.returns[:-1]:
            self.current_arg = ret_idx
            yield self
        self.current_arg = self.command.returns[-1]
        self.final = True
        yield self


class Command(Function):
    """General Command class

    Subclasses are recorded into the meta registry and can be created via
    `Command.from_dict({'class': 'DerivedCommand', ...})`.

    Attributes
    ----------
    name : string
        Name of the command function
    args : list
        List of arg sizes

    Methods
    -------
    decompile_args : list of exprs
    to_dict : dict
    """
    __metaclass__ = CommandMetaRegistry
    _fields = ('name', 'args', 'returns', 'aliases')

    def __call__(self, *args, **kwargs):
        if self.engine.state != self.engine.STATE_COMPILING:
            return
        if not self.returns:
            self.write(*args)
        else:
            ret = CommandRet(self)
            try:
                for idx in range(len(self.args)):
                    if idx in self.returns:
                        ret.args.append(0)
                    else:
                        ret.args.append(args.pop())
                if args:
                    raise IndexError
            except IndexError:
                raise TypeError(
                    '{name}() takes exactly {expect} args. ({got} given)'
                    .format(name=self.name,
                            expect=len(self.args)-len(self.returns),
                            got=len(args)))
            return ret

    def write(self, *args):
        self.engine.write_value(self.cmd_id, 2)
        expects = len(self.args)
        if len(args) != expects:
            raise TypeError(
                '{name}() takes exactly {expect} args. ({got} given)'
                .format(name=self.name,
                        expect=expects,
                        got=len(args)))
        for idx, size in enumerate(self.args):
            value = args[idx]
            if size in ('var', 'flag'):
                try:
                    size = 2
                    value = value.id
                except AttributeError:
                    # TODO: fix idx in message if self.returns
                    warnings.warn('{name}() expected a variable for arg {idx}'
                                  ' but got {var}. Casting to integer instead.'
                                  .format(name=self.name, idx=idx, var=value))
                    value = int(value)
            else:
                if (value >= 1 << (size*8)) or value < 0:
                    warnings.warn('{name}() expected arg {idx} to be in '
                                  'the range of [0, {max}) but got {var}.'
                                  ' Truncating bits.'
                                  .format(name=self.name, idx=idx,
                                          max=1 << (size*8), var=value))
            self.engine.write_value(value, size)

    def decompile_args(self, decompiler):
        """Generates decompiled command expressions by reading its arguments
        from the active decompiler

        Parameters
        ----------
        decompiler : ScriptDecompiler
            Active decompiler

        Returns
        -------
        exprs : list
            List of expressions generated. This is typically just one function.
        """
        args = []
        rets = []
        for idx, size in enumerate(self.args):
            if size == 'var':
                arg = decompiler.get_var(decompiler.read_value(2))
            elif size == 'flag':
                arg = decompiler.get_flag(decompiler.read_value(2))
            else:
                arg = decompiler.read_value(size)
                bin_arg = bin(arg)[2:-3]
                if bin_arg.count('0')*2 > bin_arg.count('1')*3 or\
                        bin_arg.count('1') > bin_arg.count('0')*3:
                    arg = hex(arg)
            if idx in self.returns:
                rets.append(arg)
            else:
                args.append(arg)
        if rets:
            if len(rets) == 1:
                rets = rets[0]
            return [decompiler.assign(rets, decompiler.func(
                self.name, *args, level=0))]
        return [decompiler.func(self.name, *args)]

    @staticmethod
    def from_dict(cmd, data):
        """Generate a Command from a dictionary

        Parameters
        ----------
        cmd : int
            Command idx
        data : dict
            Dict to generate from

        Returns
        -------
        command : Command
        """
        class_name = data.pop('class', 'Command')
        cls = CommandMetaRegistry.command_classes[class_name]
        if 'name' not in data:
            data['name'] = 'cmd_{0}'.format(cmd)
        if 'args' not in data:
            data['args'] = []
        if 'returns' not in data:
            data['returns'] = []
        if 'description' not in data:
            data['description'] = 'No description'
        if 'doc' not in data:
            doc = """{name} ({class_name})
            {name}({args}) -> {returns}

            {description}
            """.format(**dict(data, class_name=class_name))
            data['doc'] = doc
        command = cls()
        command.cmd_id = cmd
        command.__doc__ = data['doc']
        for field in cls._fields:
            setattr(command, field, data.get(field))
        return command

    def to_dict(self):
        """Saves this command back to a json-serializable dict.

        This takes all attributes from `_fields` as well as the class
        name (if not the default Command class).
        """
        command_dict = {}
        for field in self._fields:
            command_dict[field] = getattr(self, field)
        if self.__class__.__name__ != 'Command':
            command_dict['class'] = self.__class__.__name__
        return command_dict


class VariableCompare(object):
    __slots__ = ('arg1', 'arg2', 'operator')

    def __init__(self, arg1, arg2, operator):
        self.arg1 = arg1
        self.arg2 = arg2
        self.operator = operator


class ScriptVariable(Variable):
    def __lt__(self, other):
        return VariableCompare(self, other, 0)

    def __eq__(self, other):
        return VariableCompare(self, other, 1)

    def __gt__(self, other):
        return VariableCompare(self, other, 2)

    def __le__(self, other):
        return VariableCompare(self, other, 3)

    def __ge__(self, other):
        return VariableCompare(self, other, 4)

    def __ne__(self, other):
        return VariableCompare(self, other, 5)


class ScriptVariableCollection(VariableCollection):
    def _create(self, name):
        var = VariableCollection._create(self, name)
        try:
            # Variable id is assigned in named key map
            var.id = self.engine.variables[name]
        except KeyError:
            if name[:4] == 'var_':
                var.id = int(name[4:], 16)
                # TODO check bounds
            elif name[:5] == 'flag_':
                var.id = int(name[5:], 16)
            else:
                raise NameError('{name} is not a valid variable name'
                                .format(name))
        return var

    def __setattr__(self, name, value):
        if self.engine.state != self.engine.STATE_COMPILING:
            return
        var = getattr(self, name)
        try:
            value.args[value.current_arg] = var
        except AttributeError:
            pass
        else:
            if value.final:
                value.command.write(*value.args)


class StrictFunctionCollection(FunctionCollection):
    def _create(self, name):
        raise NameError('{name} is not a known function'.format(name=name))


class EndCommand(Command):
    _fields = Command._fields+('value', )

    def decompile_args(self, decompiler):
        if self.value is None:
            return [decompiler.end()]
        return [decompiler.end(self.value)]


class JumpCommand(Command):
    def decompile_args(self, decompiler):
        offset = decompiler.handle.readInt32()
        ofs2 = decompiler.tell()+offset
        return [decompiler.get_func(ofs2)]
        if offset > 0:
            decompiler.seek(decompiler.tell()+offset)
        # return [decompiler.func(self.name, offset, ofs2)]
        return []


class SetConditionCommand(Command):
    def decompile_args(self, decompiler):
        exprs = Command.decompile_args(self, decompiler)
        args = exprs[0].args  # super().get_args
        decompiler.cond_state = decompiler.statement('<=>', *args)
        # return exprs
        return []


class ConditionalJumpCommand(Command):
    def decompile_args(self, decompiler):
        oper = decompiler.handle.readUInt8()  # FIXME: Handle this...
        offset = decompiler.handle.readInt32()
        restore = decompiler.tell()
        offset += restore
        """decompiler.seek(offset)
        block = decompiler.branch_duplicate()
        block.start = offset
        # block.level = decompiler.level+1
        block.parse()
        decompiler.seek(restore)"""
        block = ExpressionBlock()
        block.lines.append(decompiler.get_func(offset))
        condition_expr = decompiler.condition(decompiler.cond_state)
        if len(condition_expr.conditional.args) == 1:
            if not oper:
                condition_expr.conditional = decompiler.func(
                    'not ', condition_expr.conditional.args[0],
                    level=0, namespace='')
        else:
            if oper == 0:
                condition_expr.conditional.operator = '<'
            elif oper == 1:
                condition_expr.conditional.operator = '=='
            elif oper == 2:
                condition_expr.conditional.operator = '>'
            elif oper == 3:
                condition_expr.conditional.operator = '<='
            elif oper == 4:
                condition_expr.conditional.operator = '>='
            elif oper == 5:
                condition_expr.conditional.operator = '!='
            else:
                raise NotImplementedError('Unknown operator: {0}'.format(oper))
        return [condition_expr, block]


class MovementCommand(Command):
    def __call__(self, overworld_id):
        if self.engine.state == self.engine.STATE_COMPILING:
            self.engine.write_value(self.cmd_id, 2)
            self.engine.write_value(overworld_id, 2)
        return self

    def decompile_args(self, decompiler):
        target = decompiler.handle.readUInt16()
        offset = decompiler.handle.readInt32()
        restore = decompiler.tell()
        offset += restore
        decompiler.seek(offset)
        block = decompiler.branch_movement()
        block.start = offset
        # block.level = decompiler.level+1
        block.parse()
        block.lines.pop()  # 0xfe
        decompiler.seek(restore)
        return [decompiler.context(decompiler.func('move', target, level=0),
                                   'movement'), block]

    def __enter__(self):
        if self.engine.state == self.engine.STATE_COMPILING:
            block = self.engine.current_block
            ofs = self.engine.tell()
            self.engine.write_value(0, 4)
            self.engine.push()
            block.jumps[ofs] = self.engine.current_block
        return self.engine.movements

    def __exit__(self, type_, value, traceback):
        if self.engine.state == self.engine.STATE_COMPILING:
            self.engine.write_value(0xfe, 2)
            self.engine.pop()


class MessageCommand(Command):
    def __call__(self, *args, **kwargs):
        if self.engine.state != self.engine.STATE_COMPILING:
            return
        text_str = kwargs.pop('text', None)
        text_id = args[0]
        if text_str:
            try:
                self.engine.text[text_id] = text_str
            except TypeError:
                warnings.warn('Text is not loaded. No text will be replaced')
            except IndexError:
                self.engine.text.populate(text_id)
                self.engine.text[text_id] = text_str
                warnings.warn('Text populated to {0}'.format(text_id))
        Command.__call__(self, *args, **kwargs)

    def decompile_args(self, decompiler):
        exprs = Command.decompile_args(self, decompiler)
        args = exprs[0].args  # super().get_args
        try:
            text_id = int(args[0])
        except:
            text_id = int(args[0], 0)
        try:
            text_str = decompiler.text[text_id]
        except IndexError:
            return exprs
        exprs[0].args = args+('text="{0}"'.format(
            text_str.encode('string_escape')), )
        return exprs


class ScriptDecompiler(Decompiler):
    def __init__(self, handle, script_container):
        Decompiler.__init__(self, handle)
        self.container = script_container
        self.commands = script_container.commands
        self.cond_state = None

    @property
    def text(self):
        if self.container.text is None:
            return []
        return self.container.text

    def parse_next(self):
        here = self.tell()
        cmd = self.read_value(2)
        if cmd is None:
            return [self.end()]
        # if cmd > max(self.commands):
        #    return [self.unknown(cmd, 2)]
        command = self.commands.get(cmd, None)
        if command is not None:
            exprs = command.decompile_args(self)
            # for expr in exprs:
            #     print(expr)
            return exprs
        return [self.unknown(cmd & 0xFF, 1), self.unknown(cmd >> 8, 1)]

    def branch_duplicate(self):
        dup = self.__class__(self.handle, self.container)
        dup.start = self.start
        return dup

    def branch_movement(self):
        dup = MovementDecompiler(self.handle, self.commands['movements'])
        dup.start = self.start
        return dup

    def get_var(self, id):
        var = Variable(id)
        var.name = 'var_{0:x}'.format(id)
        var.persist = True
        return var

    def get_flag(self, id):
        var = Variable(id)
        var.name = 'flag_{0:x}'.format(id)
        var.persist = True
        return var

    def get_func(self, offset):
        try:
            self.container.func_map[offset][1] += 1
        except:
            self.container.func_map[offset] = [None, 1, None]
        return self.wrapper(self.end(self.func('jump', offset)))


class MovementDecompiler(Decompiler):
    def __init__(self, handle, movements):
        Decompiler.__init__(self, handle)
        self.movements = movements

    def parse_next(self):
        cmd = self.read_value(2)
        if cmd is None:
            return [self.end()]
        if cmd == 0xFE:
            return [self.end()]
        command = self.movements.get(cmd)
        if command is None:
            command = 'mov_{0}'.format(cmd)
        count = self.read_value(2)
        return [self.func(command, count, namespace='movement.')]


class ScriptEngine(Engine):
    function_class = Command
    variable_class = ScriptVariable
    variable_collection_class = ScriptVariableCollection
    function_collection_class = StrictFunctionCollection
    text = ()

    def __init__(self):
        Engine.__init__(self)
        self.variables = {}
        self.movements = StrictFunctionCollection(self, Command)

    def write_end(self, value):
        if value is True:
            self.funcs.End()
        elif value is False:
            self.funcs.KillScript()
        else:
            warnings.warn('Returns should only be True/False. Assuming True')
            self.funcs.End()

    def write_branch(self, branch_state, condition):
        if branch_state is True:
            if isinstance(condition, VariableCompare):
                if isinstance(condition.arg2, Variable):
                    self.funcs.If2(condition.arg1, condition.arg2)
                else:
                    self.funcs.If(condition.arg1, condition.arg2)
                self.funcs.CheckLR(condition.operator, 0)
            else:
                # TODO: handle (not flag)
                self.funcs.Checkflag(condition)
                self.funcs.CheckLR(1, 0)
        else:
            self.funcs.Goto(0)
        return self.tell()-4

    def write_jump(self):
        self.funcs.Goto(0)
        return self.tell()-4


class Script(object):
    """Pokemon Script handler

    JSON Commands are loaded (and overwritten) in this order:
    $PPRE_DIR/data/commands/base.json
    $PPRE_DIR/data/commands/base_custom.json (optional)
    $PPRE_DIR/data/commands/$GAME_COMMAND_FILES[0], etc.
    $GAME_DIR/commands.json (optional)

    Attributes
    ----------
    scripts : list of ScriptDecompiler
        Decompiled scripts. scripts[0] will refer to script_1 because
        scripts are 1-indexed
    commands : dict
        Command map

    Parameters
    ----------
    load(reader)
        Loads a single script file in and parses its scripts
    """
    def __init__(self, game):
        self.offsets = []
        self.scripts = []
        self.compiled_scripts = []
        self.commands = {'movements': {}}
        self.variables = {}
        self.text = None
        self.game = game
        self.engine = ScriptEngine()
        self.script_start = 1  # First script ID. Scripts are 1-indexed
        self.function_start = 1  # First function ID
        self.load_commands(os.path.join(os.path.dirname(__file__), '..', '..',
                                        'data', 'commands', 'base.json'))
        try:
            self.load_commands(os.path.join(os.path.dirname(__file__), '..',
                                            '..', 'data', 'commands',
                                            'base_custom.json'))
        except IOError:
            pass
        for command_file in game.commands_files:
            self.load_commands(os.path.join(os.path.dirname(__file__), '..',
                                            '..', 'data', 'commands',
                                            command_file))
        try:
            self.load_commands(os.path.join(game.files.directory,
                                            'commands.json'))
        except IOError:
            pass

    def by_id(self, script_id):
        """Return the script by it's script_id

        Parameters
        ----------
        script_id : int
            Script ID. Finds the script whose name is script_{script_id}
            from self.scripts

        Returns
        -------
        script : ScriptDecompiler
        """
        return self.scripts[script_id-self.script_start]

    def load(self, reader):
        self.offsets = []
        self.scripts = []
        self.functions = []
        self.func_map = {}  # {offset: [func, count]}
        reader = BinaryIO.reader(reader)
        start = reader.tell()

        try:
            offset = reader.readUInt32()
        except:
            # Empty File. No script contents
            return
        while offset:
            abs_offset = offset+reader.tell()
            current_pos = reader.tell()
            for offset in self.offsets:
                if current_pos > offset:
                    break
            self.offsets.append(abs_offset)
            try:
                offset = reader.readUInt32()
            except:
                # Exhaustive offset list: not a script
                return
            if offset & 0xFFFF == 0xFD13:
                break
        if not self.offsets:
            return

        for scrnum, offset in enumerate(self.offsets, self.script_start):
            with reader.seek(offset):
                script = ScriptDecompiler(reader, self)
                script.parse()
                script.header_lines.append('def script_{num}(engine):'
                                           .format(num=scrnum))
                self.scripts.append(script)

        changed = True
        while changed:
            changed = False
            for offset, (func, count, func_id) in self.func_map.items():
                if func is None:
                    changed = True
                    with reader.seek(offset):
                        script = ScriptDecompiler(reader, self)
                        script.parse()
                        self.func_map[offset][0] = script
        cur_id = self.function_start
        embedded_functions = []
        for (offset, (func, count, func_id)) in self.func_map.items():
            if count > 1:
                func.header_lines.append('def func_{num}(engine):'
                                         .format(num=cur_id))
                self.functions.append(func)
                self.func_map[offset][2] = cur_id
                cur_id += 1
            else:
                embedded_functions.append(func)

        for script in itertools.chain(self.scripts, self.functions,
                                      embedded_functions):
            for expr in script:
                try:
                    if expr.target.args[0].name != 'jump':
                        continue
                except:
                    continue
                offset = expr.target.args[0].args[0]
                func, count, func_id = self.func_map[offset]
                if func_id is None:
                    func.indent = 0
                else:
                    end = func.lines[-1]
                    func = script.func(
                        'call', 'func_{0}'.format(func_id),
                        namespace='engine.')
                    if end.is_return() and end.args and end.args != (None, ):
                        func = script.end(func)
                expr.set_target(func)

    def save(self, writer=None):
        writer = BinaryIO(writer)
        start = writer.tell()
        if not self.compiled_scripts and self.scripts:
            handle = BinaryIO()
            self.export(handle)
            handle.seek(0)
            self.import_(handle)
        blocks = []  # set(self.engine.blocks)
        for block in self.engine.blocks:
            for used_block in blocks:
                if block == used_block:
                    break
            else:
                blocks.append(block)
        for block in self.compiled_scripts:
            writer.writeUInt32(0)
        writer.writeUInt32(0xFD13)

        for block in blocks:
            block.offset = writer.tell()-start
            writer.write(block.buff)
            writer.writeAlign(4)

        for block in blocks:
            for ofs, dest in block.jumps.items():
                for used_block in blocks:
                    if used_block == dest:
                        dest = used_block
                with writer.seek(start+block.offset+ofs):
                    writer.writeInt32(dest.offset-block.offset-ofs-4)

        with writer.seek(start):
            for block in self.compiled_scripts:
                # there is a chance that a block in the scripts got removed
                # use the actual written blocks for the relevant offsets
                for used_block in blocks:
                    if used_block == block:
                        writer.writeInt32(start+used_block.offset
                                          - writer.tell()-4)
                        break
        return writer

    def load_commands(self, fname):
        """Load commands from JSON file

        Parameters
        ----------
        fname : string
            Filename of JSON file
        """
        with open(fname) as handle:
            commands = json.load(handle)
        movements = commands.pop('movements', {})
        for cmd, command in movements.items():
            cmd = int(cmd, 0)
            self.commands['movements'][cmd] = command
            self.engine.movements._cache[command] = Command.from_dict(cmd, {
                'args': [2],
                'name': command
            })
            self.engine.movements._cache[command].engine = self.engine
        for cmd, data in commands.items():
            cmd = int(cmd, 0)
            command = self.commands[cmd] = Command.from_dict(cmd, data)
            command.engine = self.engine
            self.engine.funcs._cache[command.name] = command
            try:
                for alias in command.aliases:
                    self.engine.funcs._cache[alias] = command
            except (AttributeError, TypeError):
                pass

    def load_text(self, text):
        """Load a text archive to be associated with these scripts
        """
        self.text = text
        self.engine.text = text

    def export(self, handle):
        for script in itertools.chain(self.scripts, self.functions):
            handle.write(str(script))
            handle.write('\n\n')

    def import_(self, handle):
        """Import and compile scripts from a module.

        This does cause execution of arbitrary code (no different
        from any plugin loader though).
        """
        dynamic_script = imp.new_module('dynamic_script_')
        code = handle.read()
        six.exec_(code, dynamic_script.__dict__)
        script_funcs = {}
        for name, func in dynamic_script.__dict__.items():
            if name[:7] == 'script_':
                script_funcs[int(name[7:])] = func
        scr_idx = self.script_start
        self.compiled_scripts = []

        def script_stub(engine):
            return True

        for scr_num, func in sorted(script_funcs.items()):
            while scr_idx < scr_num:
                warnings.warn('Missing script_{0}. Generating stub'
                              .format(scr_idx))
                self.compiled_scripts.append(self.engine.compile(script_stub))
                scr_idx += 1
            self.compiled_scripts.append(self.engine.compile(func))
            scr_idx += 1


class ScriptCondition(Editable):
    def define(self):
        self.uint16('var')
        self.uint16('value')
        self.uint16('script')


class ScriptConditions(Editable):
    """Script conditions are settings that run alongside a script on a map.
    If the condition is met, the script referred to is activated.

    Conditions are located in the same archive as Scripts (they are
    not actually parseable as scripts).
    """
    def define(self, game):
        self.game = game
        self.uint16('u0')
        self.uint16('u2')
        self.uint16('u4')
        self.conditions = []
        self.restrict('conditions')

    def reset(self):
        self.u0 = self.u2 = self.u4 = 0
        self.conditions = []
        self.__getitem__ = self.conditions.__getitem__
        self.__setitem__ = self.conditions.__setitem__

    def add_condition(self, var, value, script):
        """Adds a Script Condition

        Parameters
        ----------
        var : int or Variable
            var id or var itself
        value : int
            variable value which ocndition meets
        script : int
            Script ID to be run when condition is met
        """
        cond = ScriptCondition()
        try:
            cond.var = var.id
        except AttributeError:
            cond.var = int(var)
        cond.value = value
        cond.script = script
        self.conditions.append(cond)

    def load(self, reader):
        reader = BinaryIO.reader(reader)
        self.conditions = []
        self.__getitem__ = self.conditions.__getitem__
        self.__setitem__ = self.conditions.__setitem__
        self.u0 = reader.readUInt16()
        self.u2 = reader.readUInt16()
        try:
            self.u4 = reader.readUInt16()
        except:
            self.u4 = 0
            return
        while True:
            try:
                cond = ScriptCondition()
                cond.load(reader)
                self.conditions.append(cond)
            except:
                break

    def save(self, writer=None):
        writer = BinaryIO.writer(writer)
        writer.writeUInt16(self.u0)
        writer.writeUInt16(self.u2)
        if self.conditions:
            writer.writeUInt16(self.u4)
        for cond in self.conditions:
            writer = cond.save(writer)
        writer.writeAlign(4)
        return writer


data_file_patterns = ['data/commands/*.json']
if __name__ == '__main__':
    pass
