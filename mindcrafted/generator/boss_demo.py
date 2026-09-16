"""A taught systems workshop followed by one coherent recovery encounter."""
from copy import deepcopy
from . import node_connect_demo, resource_balance_demo

NODE_TRANSFER = ('En la recuperación del archivo, Servicio A permite una capacidad de cuatro unidades en Rápido; '
                 'Servicio B permite cinco unidades en Rápido mediante su reserva adicional.')
SOURCE = node_connect_demo.SOURCE + NODE_TRANSFER + '\n' + resource_balance_demo.SOURCE


def blueprint():
    node = node_connect_demo.blueprint()['puzzles'][0]
    resource = resource_balance_demo.blueprint()['puzzles'][0]
    node['knowledge']['requiredRules'][0]['evidence'] = node_connect_demo.SOURCE + NODE_TRANSFER
    node['title'] = 'Reconectar la reserva del archivo'
    node['introduction'] = 'El archivo necesita una recuperación completa. Reconecta sus dependencias: Servicio A aporta cuatro unidades a Rápido; Servicio B aporta cinco. La ruta elegida permanecerá activa durante el reparto.'
    node['reflection'] = 'La conexión está establecida. Su reserva alimenta ahora los ejecutores; conserva esta infraestructura mientras repartes las cargas.'
    next(r for r in resource['knowledge']['requiredRules'] if r['id']=='capacity')['description'] = 'Suma por ejecutor dentro del límite visible; Rápido utiliza la reserva de la fase anterior.'
    resource['title'] = 'Estabilizar el reparto del archivo'
    resource['objective'] = 'Distribuye las cargas bajo la capacidad que proporciona la conexión anterior.'
    resource['reflection'] = 'Conexiones y reparto funcionan juntos. El archivo vuelve a prestar servicio y se abre la salida principal.'
    phases = [
        {'id':'connections','next':'distribution','puzzle':node,'bindings':[],
         'exports':[{'variable':'executor_budget','kind':'edge_present','controlId':'UI_API',
                     'cases':[{'when':True,'value':4},{'when':False,'value':5}],
                     'ruleId':'layering','evidence':NODE_TRANSFER}]},
        {'id':'distribution','next':None,'puzzle':resource,'exports':[],
         'bindings':[{'variable':'executor_budget','kind':'resource_capacity','ruleId':'capacity','targetId':'fast','evidence':NODE_TRANSFER}]},
    ]
    return {'schemaVersion':1,'id':'archive_recovery','title':'Recuperación del centro de archivo',
            'introduction':'Combina las dependencias y la distribución que ya practicaste para recuperar una única instalación.',
            'requiredSkills':sorted({r['skill'] for p in phases for r in p['puzzle']['knowledge']['requiredRules']}),
            'requiredConcepts':[p['puzzle']['knowledge']['concept'] for p in phases],
            'sharedState':[{'id':'executor_budget','label':'Capacidad de Rápido','values':[4,5]}],
            'phases':phases,'failurePolicy':'retry_current','hintPolicy':'current_phase',
            'completion':{'flag':'archive_recovered','xpBonus':125,'description':'La salida del centro de archivo y su transporte principal vuelven a funcionar.'}}


from . import machine_configuration_demo

MEMORY_TRANSFER = ('Durante la recuperación, Servicio A permite un presupuesto de ocho unidades para memoria y caché; '
                   'Servicio B permite nueve unidades mediante su reserva adicional.')
CACHE_TRANSFER = ('Durante la recuperación, el modo de caché inmediata permite cinco unidades en Rápido; '
                  'el modo de caché diferida reserva más búferes y permite cuatro unidades en Rápido.')
THREE_PHASE_SOURCE = (node_connect_demo.SOURCE + MEMORY_TRANSFER + '\n' +
                      machine_configuration_demo.SOURCE + CACHE_TRANSFER + '\n' + resource_balance_demo.SOURCE)


def three_phase_blueprint():
    result = blueprint()
    first, last = result['phases']
    first['next'] = 'configuration'
    first['puzzle']['knowledge']['requiredRules'][0]['evidence'] = node_connect_demo.SOURCE + MEMORY_TRANSFER
    first['puzzle']['introduction'] = 'El centro de archivo está detenido. Ya practicaste las dependencias, la memoria y el reparto. Conecta Servicio A para aportar ocho unidades a la estación, o Servicio B para aportar nueve. Esta elección permanecerá activa.'
    first['puzzle']['reflection'] = 'La ruta sostiene la estación de archivo. Su reserva determina cuánta memoria y caché puedes instalar. Continúa sin desconectar la infraestructura.'
    first['exports'][0].update(variable='memory_budget',evidence=MEMORY_TRANSFER,
                              cases=[{'when':True,'value':8},{'when':False,'value':9}])
    machine = machine_configuration_demo.blueprint()['puzzles'][0]
    next(r for r in machine['knowledge']['requiredRules'] if r['id']=='budget')['evidence'] = machine_configuration_demo.SOURCE + CACHE_TRANSFER
    next(r for r in machine['knowledge']['requiredRules'] if r['id']=='budget')['description'] = 'Reserva de memoria y búferes dentro del presupuesto recibido de la conexión.'
    machine['introduction'] = 'La ruta anterior alimenta esta estación. Ajusta sus componentes con el presupuesto disponible. Caché inmediata deja cinco unidades para Rápido; caché diferida reserva búferes y deja cuatro. Conserva los datos y prepara el reparto final.'
    machine['reflection'] = 'La estación conserva los datos y confirma las escrituras. Su caché establece la capacidad de Rápido para la fase final: ahora distribuye las cargas sin saturarla.'
    middle={'id':'configuration','next':'distribution','puzzle':machine,
            'bindings':[{'variable':'memory_budget','kind':'machine_capacity','ruleId':'budget','targetId':None,'evidence':MEMORY_TRANSFER}],
            'exports':[{'variable':'executor_budget','kind':'configuration_value','controlId':'cache',
                        'cases':[{'when':'writethrough','value':5},{'when':'writeback','value':4}],
                        'ruleId':'caching','evidence':CACHE_TRANSFER}]}
    last['bindings'][0]['evidence']=CACHE_TRANSFER
    last['puzzle']['introduction']='La ruta y la estación siguen activas. Distribuye Audio, Control, Informe y Copia respetando latencia y la capacidad disponible que dejó la caché. Puedes corregir esta fase sin perder la infraestructura recuperada.'
    last['puzzle']['reflection']='Las conexiones alimentan una estación consistente y el reparto respeta sus límites. El centro de archivo funciona como un único sistema; se abre el transporte principal.'
    result.update(phases=[first,middle,last],
                  introduction='Recupera una instalación completa: la ruta determina memoria; la caché determina capacidad; el reparto pone el centro de archivo en servicio.',
                  sharedState=[{'id':'memory_budget','label':'Presupuesto de memoria y caché','values':[8,9]},
                               {'id':'executor_budget','label':'Capacidad de Rápido','values':[4,5]}])
    result['requiredSkills']=sorted({r['skill'] for p in result['phases'] for r in p['puzzle']['knowledge']['requiredRules']})
    result['requiredConcepts']=[p['puzzle']['knowledge']['concept'] for p in result['phases']]
    return result
