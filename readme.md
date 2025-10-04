# Nhac Nhac


Objetivo O objetivo deste trabalho é modelar implementar um algoritmo de busca competitiva
para jogar o jogo Nhac Nhac.

O problema
Nesse trabalho você deverá desenvolver um agente inteligente capaz de jogar o jogo Nhac
Nhac. Este jogo é uma modificação do jogo da velha, onde cada jogador possui 6 peças de
tamanhos diferentes (duas grandes, duas médias e duas pequenas) e na sua vez de jogar cada
jogador pode:

1. Jogar qualquer peça disponível em uma casa vazia do tabuleiro

2. Jogar uma peça em uma casa que contenha outra peça (sua ou do adversário) e que seja
menor do que a peça que está sendo jogada, e por consequência cobrindo a peça que
estava naquela casa

3. Mover uma peça que esteja no tabuleiro (e que não tenha nenhuma peça cobrindo-a)
para outra casa (vazia ou com uma peça menor do que ela)
A regra de vitória é a mesma do jogo da velha tradicional: vence o jogador que primeiro
alinhar três peças (ambas visíveis no tabuleiro) seja na horizontal, vertical ou diagonal.
O programa a ser desenvolvido deve permitir que haja um jogador humano e um jogador
IA. Para poder participar da competição, o programa deve permitir escolher quem começa
jogando. Não é necessário desenvolver uma interface gráfica para o jogo (tarefa opcional).
O jogador IA deve tomar decisões em no máximo 30 segundos. A estratégia da IA deve ser
baseada no algoritmo Minimax ou na Busca em Árvore de Monte Carlo, com exploração limitada e utilizando uma função heurística para avaliar estados intermediários. Note que a
árvore de busca para o problema do Nhac Nhac é infinita! Seu algoritmo deve limitar a profundidade da busca para decidir qual a próxima jogada que deve ser feita